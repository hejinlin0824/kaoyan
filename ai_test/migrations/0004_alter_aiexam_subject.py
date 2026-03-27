from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("ai_test", "0003_aiexam_subject"),
    ]

    operations = [
        migrations.AlterField(
            model_name="aiexam",
            name="subject",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="kaoyan_app.subject", verbose_name="专业课"),
        ),
    ]