import json
import logging
import re
import time
import requests
from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from kaoyan_app.models import Question
from .models import AIExam, AIGeneratedQuestion, AIExamQuestion

# 配置日志记录器
logger = logging.getLogger(__name__)

# 题型名称对应 AIExam 表中的数量字段映射
TYPE_FIELD_MAP = {
    "选择": "choice_count",
    "填空": "fill_count",
    "判断": "judge_count",
    "简答": "short_count",
    "计算": "calc_count",
    "画图": "draw_count",
}

def strip_markdown_json_wrapper(text):
    """
    杀手锏二：Markdown 外衣剥离
    DeepSeek 有时不遵守 response_format，会把 JSON 包裹在 ```json ... ``` 代码块中。
    用正则自动裁剪掉外壳，提取纯 JSON 字符串。
    """
    if not text:
        return text
    # 匹配 ```json ... ``` 或 ``` ... ``` 格式
    pattern = r'^\s*```(?:json)?\s*\n?(.*?)\n?\s*```\s*$'
    match = re.match(pattern, text, re.DOTALL)
    if match:
        cleaned = match.group(1).strip()
        logger.info("      - 检测到 Markdown 代码块包裹，已自动剥离。")
        return cleaned
    return text


def fix_invalid_json_escapes(text):
    """
    杀手锏三：Python 层正则自动修复非法 JSON 转义（终极兜底）
    LaTeX 公式中的 \\frac, \\sin 等单反斜杠在 JSON 中不合法。
    将非法的反斜杠+字母（如 \\frac）替换为双反斜杠形式。
    注意：必须保护已经合法的转义序列（\\\\, \", \\/, \\n, \\r, \\t, \\b, \\f, \\uXXXX）不被误伤。
    """
    if not text:
        return text
    # 合法的 JSON 转义字符集合
    valid_escapes = set('"\\/\n\r\tbfu')
    result = []
    i = 0
    fixed_count = 0
    while i < len(text):
        if text[i] == '\\' and i + 1 < len(text):
            next_char = text[i + 1]
            if next_char in valid_escapes:
                # 合法转义，原样保留
                if next_char == 'u' and i + 5 < len(text):
                    # \uXXXX 形式，整体保留
                    result.append(text[i:i + 6])
                    i += 6
                else:
                    result.append(text[i:i + 2])
                    i += 2
            else:
                # 非法转义（如 \frac, \sin, \alpha 等），补一个反斜杠
                result.append('\\\\')
                result.append(next_char)
                i += 2
                fixed_count += 1
        else:
            result.append(text[i])
            i += 1
    if fixed_count > 0:
        logger.info(f"      - 正则修复了 {fixed_count} 处非法 LaTeX 反斜杠转义。")
    return ''.join(result)


def safe_parse_json(text):
    """
    安全 JSON 解析器（三重防御）：
    1. 先直接解析
    2. 失败则剥离 Markdown 外衣后重试
    3. 再失败则修复非法转义后重试
    """
    # 第一层：直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 第二层：剥离 Markdown 代码块后解析
    stripped = strip_markdown_json_wrapper(text)
    if stripped != text:
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

    # 第三层：修复非法转义后解析（先剥离再修复）
    fixed = fix_invalid_json_escapes(stripped)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # 第四层：对原始文本也尝试修复（以防剥离后反而破坏了结构）
    fixed_original = fix_invalid_json_escapes(text)
    if fixed_original != text:
        try:
            return json.loads(fixed_original)
        except json.JSONDecodeError:
            pass

    # 全部失败
    return None


def mask_api_key(key):
    """将 API Key 脱敏，方便在日志中安全打印"""
    if not key:
        return "未配置或为空"
    if len(key) > 8:
        return f"{key[:4]}......{key[-4:]}"
    return "***"

def call_llm_for_variant(original_question, current_index, total_needed):
    """
    核心 AI Agent 调用服务：
    请求大模型对给定真题进行同义改写与考法变式，带详尽日志。
    """
    logger.info(f"  >>> [进度 {current_index}/{total_needed}] 准备改写原题 ID: {original_question.id} | 知识点: {original_question.knowledge_point}")
    
    prompt = f"""你是一个考研出题专家。你的任务是【深度变式出题】，绝不是简单改写文字！

【核心要求】
你必须先彻底理解原题考的是什么知识点，然后用不同的具体数值、函数表达式、条件或场景，重新出一道考同一个知识点的同类型题。禁止原封不动搬运！

【变式方法（必须使用）】
- 如果题中有具体数值（如 2、3、5），换成其他合理的数值
- 如果题中有函数（如 cos、sin、e^x），换成同类的其他函数
- 如果题中有参数（如 ω、α、k），改变参数的值或换一个参数
- 如果题中有条件（如"大于0"、"连续"、"可导"），适当调整条件
- 如果题中有图形描述，改变图形的具体形状或参数
- 你可以改变正确选项的位置（选择题）

【变式示例】
原判断题：f(t)=|cos(ωt)| 的直流分量为0
✗ 错误变式：f(t)=|cos(ωt)| 的直流分量不为0（只改了结论，太弱）
✓ 正确变式：f(t)=|sin(2ωt)| 的直流分量为0
✓ 正确变式：f(t)=cos²(3t) 的直流分量为1/2

原选择题：设函数 f(x)=x²-2x+1 在 x=1 处的导数值为
✗ 错误变式：设函数 f(x)=x²-2x+1 在 x=1 处的导数值为（原题照搬）
✓ 正确变式：设函数 f(x)=x³-3x² 在 x=2 处的导数值为

原填空题：∫₀¹ x dx 的值为
✗ 错误变式：∫₀¹ x dx 的值为（原题照搬）
✓ 正确变式：∫₀² x² dx 的值为

【输出要求】
1. 必须以严格 JSON 格式返回，包含三个字段：
   - "content"（字符串）：变式后的题干
   - "options"（字典，无选项则 null）：选择题的选项
   - "correct_answer"（字符串或null）：选择题填正确选项字母如"A"，判断题填"对"或"错"，填空题填标准答案（多空用分号分隔），简答/计算/画图题填null
2. 【极其重要】所有 LaTeX 公式必须用 $ 符号包裹！例如：$f(t)=\\delta''(t)+3\\delta(t)$，$\\int_0^1 x\\,dx$，$\\frac{{a}}{{b}}$。不能出现裸露的反斜杠命令！
3. 【极其重要】LaTeX 公式中的反斜杠必须双写转义（因为是在 JSON 字符串内），如 \\\\frac、\\\\sin、\\\\int、\\\\delta
4. 【极其重要】直接输出裸 JSON，不要用 ```json 包裹

【公式格式示例】
正确写法：已知 $f(t) = \\delta''(t) + 3\\delta(t)$，求 $f(t)$ 的拉氏变换
错误写法：已知 f(t) = \\delta''(t)（缺少 $ 包裹且反斜杠未双写）

原题内容：
{original_question.content}

原题选项：
{json.dumps(original_question.options, ensure_ascii=False) if original_question.options else 'null'}
"""

    try:
        # 获取并打印配置（脱敏），方便排查环境是否生效
        application_identity = getattr(settings, 'APPLICATION_IDENTITY', '')
        api_url = getattr(settings, 'LLM_API_URL', 'https://api.openai.com/v1/chat/completions')
        model_name = getattr(settings, 'LLM_MODEL_NAME', 'gpt-4o')
        
        logger.info(f"      - API 地址: {api_url}")
        logger.info(f"      - 模型名称: {model_name}")
        logger.info(f"      - 鉴权密钥: {mask_api_key(application_identity)}")
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {application_identity}"
        }
        
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "你是一个考研变式出题专家。你的核心能力是理解一道题的知识点，然后换汤不换药地出一道全新的同类型题。你必须改变原题中的具体数值、函数、参数或条件，但保持考查的知识点完全一致。绝对禁止原题照搬。同时你必须严格以 JSON 格式输出。"},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.7
        }
        
        logger.info("      - 发起网络请求...")
        start_time = time.time()
        
        response = requests.post(api_url, headers=headers, json=payload, timeout=45)
        
        # 抛出 HTTP 错误（如 401, 404, 500等）
        response.raise_for_status()
        
        elapsed_time = time.time() - start_time
        logger.info(f"      - 请求成功！耗时: {elapsed_time:.2f} 秒")
        
        result_text = response.json()["choices"][0]["message"]["content"]
        logger.debug(f"      - 模型原始返回: {result_text}")
        
        # 使用安全 JSON 解析器（三重防御：直接解析 → 剥离Markdown → 修复LaTeX转义）
        result_data = safe_parse_json(result_text)
        
        if result_data is None:
            logger.error("      ❌ 安全 JSON 解析器四层防御全部失败，无法解析模型返回内容。")
            logger.warning("      ⚠️ 触发降级机制：直接使用原题内容。")
            return original_question.content, original_question.options, original_question.correct_answer
        
        new_content = result_data.get("content", original_question.content)
        new_options = result_data.get("options", original_question.options)
        new_correct_answer = result_data.get("correct_answer", None)
        
        logger.info("      - JSON 数据解析并提取成功！")
        return new_content, new_options, new_correct_answer
        
    except requests.exceptions.HTTPError as e:
        logger.error(f"      ❌ HTTP 请求错误 (状态码: {e.response.status_code}): {e.response.text}")
        logger.warning("      ⚠️ 触发降级机制：直接使用原题内容。")
        return original_question.content, original_question.options, original_question.correct_answer
    except requests.exceptions.RequestException as e:
        logger.error(f"      ❌ 网络或连接错误: {str(e)}")
        logger.warning("      ⚠️ 触发降级机制：直接使用原题内容。")
        return original_question.content, original_question.options, original_question.correct_answer
    except Exception as e:
        logger.error(f"      ❌ 发生未知异常: {str(e)}")
        logger.warning("      ⚠️ 触发降级机制：直接使用原题内容。")
        return original_question.content, original_question.options, original_question.correct_answer


@shared_task
def generate_ai_exam_task(exam_id):
    """
    异步 AI 组卷任务：
    根据用户提交的各题型数量，从真题库抽题，调用大模型进行改写，并装配入独立的 AI 试卷及题库中。
    """
    logger.info("=" * 50)
    logger.info(f"🚀 开始执行 AI 组卷任务 | 试卷ID: {exam_id}")
    logger.info("=" * 50)
    
    try:
        exam = AIExam.objects.get(id=exam_id)
    except AIExam.DoesNotExist:
        logger.error(f"❌ AIExam 实例不存在，任务强行终止。ID: {exam_id}")
        return

    # 计算总共需要生成的题目数量
    total_needed_questions = sum(getattr(exam, field, 0) for field in TYPE_FIELD_MAP.values())
    logger.info(f"📊 本次组卷共需生成题目总数: {total_needed_questions} 道")
    
    if total_needed_questions == 0:
        logger.warning("⚠️ 需要生成的题目数为 0，直接将试卷标记为已完成。")
        exam.status = "completed"
        exam.completed_at = timezone.now()
        exam.save(update_fields=["status", "completed_at"])
        return

    order = 1
    
    # 开启事务，确保试卷题目生成及状态变更的数据一致性
    with transaction.atomic():
        for type_name, count_field in TYPE_FIELD_MAP.items():
            needed = getattr(exam, count_field, 0)
            if needed <= 0:
                continue
                
            logger.info(f"🔎 正在抽取【{type_name}】题库候选数据，需 {needed} 道...")
            
            # 严格过滤掉所有带有插图的题目
            candidates = list(
                Question.objects.select_related("school", "question_type")
                .filter(question_type__name=type_name)
                .filter(Q(image__isnull=True) | Q(image__exact=''))
                .order_by("?")[:needed]
            )
            
            if len(candidates) < needed:
                logger.warning(f"⚠️ 题库中无图的【{type_name}】仅有 {len(candidates)} 道，少于所需的 {needed} 道！")
            
            for orig_q in candidates:
                # 1. 调用 AI Agent 生成变式
                new_content, new_options, new_correct_answer = call_llm_for_variant(orig_q, order, total_needed_questions)
                
                # 2. 写入独立的 AI 练习题库
                logger.info(f"      - 正在存入独立 AI 题库 (AIGeneratedQuestion)...")
                ai_q = AIGeneratedQuestion.objects.create(
                    original_question=orig_q,
                    year=orig_q.year,
                    school=orig_q.school,
                    question_type=orig_q.question_type,
                    difficulty=orig_q.difficulty,
                    knowledge_point=orig_q.knowledge_point,
                    content=new_content,
                    options=new_options,
                    correct_answer=new_correct_answer,
                )
                
                # 3. 关联到当前正在生成的 AI 试卷
                logger.info(f"      - 正在建立试卷关联关系...")
                AIExamQuestion.objects.create(
                    exam=exam,
                    question=ai_q,
                    order=order
                )
                logger.info(f"      ✅ 第 {order} 题处理完毕。\n")
                order += 1
                
        # 4. 任务完成，更新试卷状态与时间
        exam.status = "completed"
        exam.completed_at = timezone.now()
        exam.save(update_fields=["status", "completed_at"])
        
    logger.info("=" * 50)
    logger.info(f"🎉 AI 组卷任务全部完成！试卷ID: {exam_id}，实际成功装配 {order - 1} 道题。")
    logger.info("=" * 50)