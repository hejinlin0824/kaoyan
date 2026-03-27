from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("kaoyan_app", "0005_subject_question_subject"),
    ]

    operations = [
        migrations.AlterField(
            model_name="question",
            name="subject",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="kaoyan_app.subject", verbose_name="专业课"),
        ),
    ]