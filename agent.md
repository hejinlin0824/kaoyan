# Agent 指南 - 考研平台 (kaoyan)

## 项目概述

这是一个基于 **Django 6.0.3** 的考研刷题与智能组卷平台，主要面向考研学生提供真题查询、手动组卷练习、AI 变式出题等功能。项目使用 Python，数据库为 SQLite3，异步任务队列使用 Celery + Redis，AI 能力通过 DeepSeek 大模型 API 实现。

## 技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python 3.x |
| Web 框架 | Django 6.0.3 |
| 数据库 | SQLite3 (`db.sqlite3`) |
| 异步任务 | Celery + Redis (db2 做 broker, db3 做 backend) |
| AI 模型 | DeepSeek (`deepseek-chat`)，通过 OpenAI 兼容 API 调用 |
| 前端 | 纯 Django 模板 + 内联 CSS，无前端框架 |
| 数学公式 | Markdown + LaTeX (`$...$` 行内, `$$...$$` 块级) |
| 部署 | 开发服务器 `runserver 0.0.0.0:8327`，通过 `start.sh` 管理 |

## 项目结构

```
kaoyan/
├── manage.py                    # Django 管理入口
├── start.sh                     # 一键启动/停止脚本 (Django + Celery)
├── start.txt                    # 启动命令备忘
├── bak.json                     # 题库 JSON 备份（信号自动同步）
├── .gitignore
├── kaoyan_project/              # Django 项目配置
│   ├── settings.py              # 核心配置（含 LLM API、Celery 配置）
│   ├── urls.py                  # 根 URL 路由分发
│   ├── celery.py                # Celery 实例与自动发现配置
│   └── __init__.py              # 导出 celery_app
├── user/                        # 用户模块
│   ├── models.py                # 自定义 User 模型（含 VIP 字段）
│   ├── views.py                 # 首页、注册、登录、登出、VIP 页面
│   ├── forms.py                 # RegisterForm, LoginForm
│   ├── urls.py                  # app_name="user"
│   └── templates/user/          # base.html (全局基础模板), home.html, login.html, register.html, vip.html
├── kaoyan_app/                  # 真题题库模块
│   ├── models.py                # Subject, School, QuestionType, Question
│   ├── views.py                 # 题目列表(公开)、增删改(管理员)
│   ├── forms.py                 # QuestionForm (含选项拆分逻辑), QuestionSearchForm
│   ├── signals.py               # 题目增删时自动备份到 bak.json
│   ├── urls.py                  # app_name="kaoyan"
│   └── templates/kaoyan/        # question_list.html, question_form.html, question_confirm_delete.html
├── zu_juan/                     # 手动组卷模块
│   ├── models.py                # Exam, ExamQuestion, WrongQuestion
│   ├── views.py                 # 组卷、预览、作答、提交阅卷、结果、错题本
│   ├── forms.py                 # ExamCreateForm
│   ├── urls.py                  # app_name="zu_juan", 前缀 /exam/
│   └── templates/zu_juan/       # exam_create.html, exam_preview.html, exam_take.html, exam_result.html, wrong_book.html
├── ai_test/                     # AI 智能组卷模块
│   ├── models.py                # AIGeneratedQuestion, AIExam, AIExamQuestion
│   ├── views.py                 # AI组卷入口、试卷列表、状态轮询API、作答页
│   ├── tasks.py                 # Celery 异步任务：抽题 + 调用 LLM 改写 + 装配试卷
│   ├── forms.py                 # AIExamCreateForm
│   ├── urls.py                  # app_name="ai_test", 前缀 /ai-test/
│   └── templates/ai_test/       # ai_exam_create.html, ai_exam_list.html, ai_exam_take.html
├── makdown/                     # 考研真题 Markdown 文档（数据来源参考）
│   ├── xjdx-2023.md
│   └── xjdx-2024.md
└── static/                      # 静态资源
    └── images/
```

## URL 路由总表

| URL 模式 | 命名空间:名称 | 说明 | 权限 |
|----------|---------------|------|------|
| `/` | `user:home` | 首页 | 公开 |
| `/register/` | `user:register` | 注册 | 公开 |
| `/login/` | `user:login` | 登录 | 公开 |
| `/logout/` | `user:logout` | 登出 | 登录 |
| `/vip/` | `user:vip` | VIP 开通页 | 公开 |
| `/questions/` | `kaoyan:question_list` | 题目列表（含搜索筛选） | 公开 |
| `/questions/add/` | `kaoyan:question_add` | 添加题目 | 管理员 |
| `/questions/<pk>/edit/` | `kaoyan:question_edit` | 编辑题目 | 管理员 |
| `/questions/<pk>/delete/` | `kaoyan:question_delete` | 删除题目 | 管理员 |
| `/exam/create/` | `zu_juan:exam_create` | 手动组卷 | VIP |
| `/exam/preview/<pk>/` | `zu_juan:exam_preview` | 试卷预览 | VIP |
| `/exam/take/<pk>/` | `zu_juan:exam_take` | 在线作答 | VIP |
| `/exam/submit/<pk>/` | `zu_juan:exam_submit` | 提交阅卷 (POST) | VIP |
| `/exam/result/<pk>/` | `zu_juan:exam_result` | 阅卷结果 | VIP |
| `/exam/wrong-book/` | `zu_juan:wrong_book` | 错题本 | VIP |
| `/ai-test/create/` | `ai_test:ai_exam_create` | AI 智能组卷 | VIP |
| `/ai-test/list/` | `ai_test:ai_exam_list` | AI 试卷列表 | VIP |
| `/ai-test/status/<pk>/` | `ai_test:ai_exam_status` | 状态轮询 API (JSON) | 登录 |
| `/ai-test/take/<pk>/` | `ai_test:ai_exam_take` | AI 试卷作答 | VIP |
| `/ai-test/practice/create/` | `ai_test:ai_practice_create` | AI题库组卷 | VIP |
| `/ai-test/practice/list/` | `ai_test:ai_practice_list` | AI题库练习卷列表 | VIP |
| `/ai-test/practice/<pk>/preview/` | `ai_test:ai_practice_preview` | AI练习卷预览 | VIP |
| `/ai-test/practice/<pk>/take/` | `ai_test:ai_practice_take` | AI练习卷作答 | VIP |
| `/ai-test/practice/<pk>/submit/` | `ai_test:ai_practice_submit` | AI练习卷提交阅卷 (POST) | VIP |
| `/ai-test/practice/<pk>/result/` | `ai_test:ai_practice_result` | AI练习卷阅卷结果 | VIP |
| `/ai-test/wrong-book/` | `ai_test:ai_wrong_book` | AI错题本 | VIP |

## 数据模型详解

### user.User（自定义用户模型）

继承 `AbstractUser`，增加 VIP 功能：

| 字段 | 类型 | 说明 |
|------|------|------|
| `vip_level` | IntegerField | 0=普通, 1=月度, 2=季度, 3=年度 |
| `vip_start_date` | DateTimeField | VIP 开通时间 |
| `vip_expire_date` | DateTimeField | VIP 过期时间 |

关键方法：`is_vip()` — 判断当前是否为有效 VIP（level>0 且未过期）。

> **注意**：`AUTH_USER_MODEL = 'user.User'`，所有外键引用用户时使用 `settings.AUTH_USER_MODEL`。

### kaoyan_app.Subject

专业课维度表，`name` 字段唯一。现有数据：信号与系统。题目、组卷、AI 组卷均按专业课维度隔离。

### kaoyan_app.School

学校维度表，`name` 字段唯一。

### kaoyan_app.QuestionType

题型维度表，现有题型：选择、填空、判断、简答、计算、画图。

### kaoyan_app.Question（核心题目模型）

| 字段 | 类型 | 说明 |
|------|------|------|
| `subject` | FK → Subject | 所属专业课（必填） |
| `year` | IntegerField | 考试年份 |
| `school` | FK → School | 所属学校 |
| `question_type` | FK → QuestionType | 题型 |
| `difficulty` | CharField | 易/中/难 |
| `knowledge_point` | CharField | 知识点描述 |
| `content` | TextField | 题干（Markdown + LaTeX） |
| `options` | JSONField | 选项，格式 `{"A":"...", "B":"...", "C":"...", "D":"..."}`，非选择题为 null |
| `correct_answer` | TextField | 正确答案（选择填A/B/C/D，判断填对/错，填空用分号分隔，主观题可留空） |
| `answer` | TextField | 答案解析（Markdown + LaTeX） |
| `image` | ImageField | 插图，上传到 `questions/%Y/%m/` |

> **兼容性注意**：旧数据的 `options` 可能是数组格式（如 `["A. xxx", "B. xxx"]`），在 `question_list` 视图和 `question_edit` 视图中做了兼容转换。

### zu_juan.Exam（试卷）

| 字段 | 类型 | 说明 |
|------|------|------|
| `user` | FK → User | 所属用户 |
| `status` | CharField | preview/taking/submitted |
| `duration_seconds` | IntegerField | 作答时长 |
| `score` | IntegerField | 客观题得分 |
| `total_objective_score` | IntegerField | 客观题总分 |
| `choice_count` ~ `draw_count` | IntegerField | 各题型数量快照 |

### zu_juan.ExamQuestion（试卷-题目关联）

| 字段 | 类型 | 说明 |
|------|------|------|
| `exam` | FK → Exam | 所属试卷 |
| `question` | FK → Question | 关联真题 |
| `order` | IntegerField | 题目顺序 |
| `user_answer` | TextField | 用户答案 |
| `is_correct` | BooleanField | 是否正确（仅客观题） |
| `score` | IntegerField | 得分 |

唯一约束：`(exam, question)`。分值规则：选择5分、填空5分、判断3分、主观题0分。

### zu_juan.WrongQuestion（错题本）

| 字段 | 类型 | 说明 |
|------|------|------|
| `user` | FK → User | 所属用户 |
| `question` | FK → Question | 关联真题 |
| `error_count` | IntegerField | 错误次数（F表达式自增） |
| `last_wrong_at` | DateTimeField | 最近错误时间 |

唯一约束：`(user, question)`。

### ai_test.AIGeneratedQuestion（AI 变式题目，独立题库）

与 `Question` 结构类似但**独立存储**，不污染原题库。关键区别：

| 字段 | 类型 | 说明 |
|------|------|------|
| `original_question` | FK → Question (SET_NULL) | 溯源真题（原题删除不影响） |
| `content` | TextField | AI 改写后的题干 |
| `options` | JSONField | AI 生成的选项 |
| `correct_answer` | TextField | AI 生成的正确答案 |
| 无 `answer` 字段 | — | 不含答案解析 |
| 无 `image` 字段 | — | 不含插图 |

### ai_test.AIExam / AIExamQuestion

与 `zu_juan.Exam / ExamQuestion` 结构类似，但关联的是 `AIGeneratedQuestion` 而非 `Question`。`AIExam` 多了 `task_id`（Celery 任务 ID）、`completed_at` 字段和 `subject`（FK → Subject，按专业课隔离抽题）。`AIExamQuestion` 无 `is_correct` 和 `score` 字段（AI 试卷为纯练习模式，不阅卷）。

### ai_test.AIPracticeExam / AIPracticeExamQuestion（AI题库组卷）

从 `AIGeneratedQuestion` 中同步抽题组卷（不调LLM），结构与 `zu_juan.Exam / ExamQuestion` 类似但关联 `AIGeneratedQuestion`。支持自动阅卷（选择5分、填空5分、判断3分、主观题0分），无每日次数限制，仅要求VIP。`AIPracticeExamQuestion` 唯一约束 `(exam, question)`。

### ai_test.AIWrongQuestion（AI错题本）

| 字段 | 类型 | 说明 |
|------|------|------|
| `user` | FK → User | 所属用户 |
| `question` | FK → AIGeneratedQuestion | 关联AI题目 |
| `error_count` | IntegerField | 错误次数（F表达式自增） |
| `last_wrong_at` | DateTimeField | 最近错误时间 |

唯一约束：`(user, question)`。与 `zu_juan.WrongQuestion` 独立，互不影响。

## 核心业务流程

### 1. 题目录入流程（管理员）

```
管理员登录 → /questions/add/ → 选择专业课 → 填写表单 → QuestionForm.clean() 合并四个选项字段为 JSON 字典 → 保存 → 信号触发 → bak.json 自动备份
```

### 2. 手动组卷流程（VIP 用户）

```
/exam/create/ → 选择专业课 → 配置各题型数量 → 按专业课随机抽题 → /exam/preview/<pk>/ → /exam/take/<pk>/ → POST /exam/submit/<pk/> → 自动阅卷(客观题) → 错题入库 → /exam/result/<pk/>
```

阅卷逻辑：
- **选择题**：用户答案大写匹配正确答案
- **判断题**：精确匹配 "对"/"错"
- **填空题**：按分号拆分，逐空比对（忽略大小写）
- **主观题**（简答/计算/画图）：不自动评分，`is_correct=null`

### 3. AI 智能组卷流程（VIP 用户）

```
/ai-test/create/ → 选择专业课 → 配置各题型数量 → 创建 pending 状态 AIExam → Celery 任务入队 → 立即跳转列表页
                                                                            ↓
前端 AJAX 轮询 /ai-test/status/<pk>/ ←←←←←←←←←←←←←←←←←←← Celery Worker 异步执行：
                                                                            ↓
                                                                    按专业课+题型从题库随机抽题（排除有图的题）
                                                                    ↓
                                                                    逐题调用 DeepSeek API 改写
                                                                    ↓
                                                                    写入 AIGeneratedQuestion（独立表）
                                                                    ↓
                                                                    关联到 AIExamQuestion
                                                                    ↓
                                                                    更新 AIExam 状态为 completed
                                                                            ↓
前端检测到 completed → 显示"进入练习"按钮 → /ai-test/take/<pk/> → 纯净练习（无阅卷）
```

### 4. AI 改写降级策略

当 LLM 调用失败时（网络错误、JSON 解析失败等），自动降级为使用原题内容，确保试卷一定能生成完成。JSON 解析有四层防御：
1. 直接 `json.loads()`
2. 剥离 Markdown 代码块后重试
3. 修复非法 LaTeX 反斜杠转义后重试
4. 对原始文本也尝试修复后重试

## 权限体系

| 装饰器 | 作用 | 定义位置 |
|--------|------|----------|
| `@login_required` | 要求登录 | Django 内置 |
| `@user_passes_test(is_admin)` | 要求 `is_staff=True` | `kaoyan_app/views.py` |
| `@vip_required` | 要求有效 VIP，否则跳转 VIP 页 | `zu_juan/views.py`（被 `ai_test` 复用） |

## 关键配置（settings.py）

```python
AUTH_USER_MODEL = 'user.User'           # 自定义用户模型
LANGUAGE_CODE = 'zh-hans'               # 中文
TIME_ZONE = 'Asia/Shanghai'             # 东八区

# Cookie 名称（避免同一域名下多个 Django 项目冲突）
SESSION_COOKIE_NAME = "kaoyan_sessionid"
CSRF_COOKIE_NAME = "kaoyan_csrftoken"

# LLM 配置
APPLICATION_IDENTITY = "sk-..."         # DeepSeek API Key
LLM_API_URL = "https://api.deepseek.com/chat/completions"
LLM_MODEL_NAME = "deepseek-chat"

# Celery 配置
CELERY_BROKER_URL = 'redis://127.0.0.1:6379/2'
CELERY_RESULT_BACKEND = 'redis://127.0.0.1:6379/3'
```

## 启动与运维

```bash
# 激活虚拟环境
source /home/ubuntu/home/ENVS/kaoyan/bin/activate

# 一键管理（推荐）
./start.sh start    # 启动 Django(8327) + Celery
./start.sh stop     # 停止
./start.sh restart  # 重启
./start.sh status   # 状态
./start.sh log      # 查看日志

# 手动启动
python manage.py runserver 0.0.0.0:8327
celery -A kaoyan_project worker -l INFO -n kaoyan_worker@%h

# 数据库迁移
python manage.py makemigrations
python manage.py migrate

# 创建超级管理员
python manage.py createsuperuser
```

日志文件位于 `.logs/django.log` 和 `.logs/celery.log`，PID 文件位于 `.pids/`。

## 前端架构

- **无前端构建工具**，纯 Django 模板渲染
- 全局基础模板：`user/templates/user/base.html`，定义了导航栏、CSS 变量体系和通用组件样式
- **设计风格**：蓝白色系专业风格，使用 CSS 自定义属性（`--blue-*`, `--gray-*`, `--white`, `--shadow`, `--radius`）统一色彩
- **图标**：Font Awesome 6 CDN（`fa-solid` 系列），替代所有 emoji
- **数学公式渲染**：使用 KaTeX CDN（非 MathJax），配合 marked.js（Markdown 解析）和 DOMPurify（XSS 防护）实现客户端渲染
  - LaTeX 占位符替换流程：先提取 `$...$`、`$$...$$`、`\(...\)`、`\[...\]` 为占位符 → marked 解析 → KaTeX 渲染回填 → DOMPurify 清洗
  - KaTeX 标签和属性已完整加入 DOMPurify 白名单
  - 使用到的模板：`question_list.html`、`question_form.html`
- **CSS 组件类**：
  - `.card` — 白色圆角卡片，带细边框和阴影
  - `.btn` / `.btn-primary` / `.btn-outline` / `.btn-danger` / `.btn-ghost-*` — 按钮系列
  - `.form-group` / `.form-input` / `.form-error` / `.form-errors-all` — 表单系列
  - `.page-header` / `.page-title` / `.page-subtitle` — 页面标题
  - `.tag` / `.tag-blue` / `.tag-green` / `.tag-amber` / `.tag-red` / `.tag-purple` — 标签系列
  - `.empty-state` — 空状态提示
  - `.pagination` — 分页组件
  - `.mt-16` / `.mt-24` — 间距工具类（margin-top 16px/24px）
- **模板继承链**：所有页面模板 → `user/base.html`，使用 `{% block title %}`、`{% block content %}`、`{% block extra_style %}` 三个 block
- 表单提交均使用传统 POST 方式（非 AJAX），AI 试卷列表页的进度轮询是唯一的 AJAX 交互

## 开发原则

1. **非必须不新建 App**：优先在现有 app 中扩展功能，复用已有模型、表单、视图和模板。只有当新功能在逻辑上完全独立、与任何现有 app 无关联时才考虑新建 app。能复用就复用。
2. **功能入口必须有导航**：新增功能页面必须在导航栏和/或主页有明确入口，不能出现"做了页面但找不到入口"的情况。
3. **遵循现有模式**：新增功能应参考项目中已有的同类型功能实现方式，保持代码风格、命名规范、模板结构一致。

## 开发注意事项

1. **自定义用户模型**：所有 `ForeignKey(User)` 必须用 `settings.AUTH_USER_MODEL`，不能直接引用 `User` 类
2. **选项格式兼容**：`Question.options` 存在字典和数组两种历史格式，新增/修改时统一用字典格式，读取时需做兼容处理
3. **信号备份**：`kaoyan_app/signals.py` 在每次题目增删时全量重写 `bak.json`，题目量大时可能有性能影响
4. **AI 任务无重试**：Celery 任务未配置 `autoretry_for`，LLM 调用失败直接降级，不会重试
5. **AI 抽题排除图片题**：`generate_ai_exam_task` 中用 `Q(image__isnull=True) | Q(image__exact='')` 过滤，确保 AI 改写不涉及图片
6. **错题去重**：`WrongQuestion` 使用 `(user, question)` 唯一约束，重复做错用 `F("error_count") + 1` 原子更新
7. **静态文件**：`STATICFILES_DIRS` 包含 `static/` 目录，`STATIC_ROOT` 为 `staticfiles/`
8. **媒体文件**：上传的图片存储在 `media/` 目录，DEBUG 模式下通过 URL 直接访问
9. **数据库**：使用 SQLite3，不适合高并发生产环境
10. **VIP 装饰器复用**：`ai_test/views.py` 从 `zu_juan/views.py` 导入 `vip_required`，修改时注意两边影响

## 常见开发任务

### 添加新专业课
1. 在 Django Admin 或数据库中添加 `Subject` 记录
2. 题目录入时选择对应专业即可，无需其他改动

### 添加新题型
1. 在 Django Admin 或数据库中添加 `QuestionType` 记录
2. 在 `zu_juan/views.py` 的 `TYPE_FIELD_MAP`、`SCORE_MAP`、`OBJECTIVE_TYPES` 中添加映射
3. 在 `ai_test/tasks.py` 的 `TYPE_FIELD_MAP` 中添加映射
4. 在 `zu_juan/forms.py` 和 `ai_test/forms.py` 的 `LIMITS` 中添加限制
5. 在 `Exam` 和 `AIExam` 模型中添加对应的 `xxx_count` 字段并迁移

### 修改 AI Prompt
编辑 `ai_test/tasks.py` 中的 `call_llm_for_variant` 函数内的 `prompt` 字符串。

### 修改阅卷逻辑
编辑 `zu_juan/views.py` 中的 `exam_submit` 视图函数。

### 添加新页面
1. 在对应 app 的 `views.py` 添加视图函数
2. 在对应 app 的 `urls.py` 注册路由
3. 在 `templates/` 下创建 HTML 模板，继承 `user/base.html`