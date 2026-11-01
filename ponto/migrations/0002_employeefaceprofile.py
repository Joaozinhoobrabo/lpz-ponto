import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ponto", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="EmployeeFaceProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("face_encoding", models.JSONField(default=list, help_text="Lista com 128 valores do encoding facial", verbose_name="vetor facial")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="criado em")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="atualizado em")),
                (
                    "employee",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="face_profile",
                        to="ponto.employee",
                        verbose_name="funcionário",
                    ),
                ),
            ],
            options={
                "verbose_name": "perfil facial",
                "verbose_name_plural": "perfis faciais",
            },
        ),
    ]
