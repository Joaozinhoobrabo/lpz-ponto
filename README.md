# LPZ Ponto

Aplicação web acadêmica para apoiar o controle de jornada da LPZ Montagens Industriais. A versão inicial cobre login, cadastro administrativo de funcionários e jornadas, registro de ponto no servidor e consulta ao histórico. Os cálculos são informativos e não substituem conferência trabalhista ou folha oficial.

## Arquitetura

- `accounts`: usuário autenticado pelo Django e perfil (`admin`, `hr` ou `employee`).
- `ponto`: equipes, jornadas, funcionários, dias e eventos de ponto imutáveis; regras de sequência ficam em `services.py`.
- `config`: configurações para execução local e produção. SQLite é usado por padrão; `DATABASE_URL` habilita PostgreSQL.
- `templates/` e `static/`: interface responsiva em português, JavaScript da tela de ponto e estilos.

O funcionário consulta apenas o próprio histórico. Administradores consultam toda a empresa; RH/gestores ficam limitados à equipe associada ao seu cadastro. O horário oficial usa `timezone.now()` no servidor, com timezone configurável (`TIME_ZONE`, padrão `America/Sao_Paulo`). A localização só é solicitada quando o funcionário envia uma marcação. Coordenadas não são inventadas nem coletadas continuamente; sua obrigatoriedade é configurável por `PUNCH_REQUIRE_GEOLOCATION`.

## macOS: executar localmente

Requer Python 3.10 ou superior. No terminal, dentro desta pasta:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
set -a; source .env; set +a
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Acesse `http://127.0.0.1:8000/`. O primeiro administrador pode cadastrar equipes e jornadas em `/admin/`, criar usuários com o perfil apropriado e depois associar usuários e funcionários na área administrativa. O cadastro inicial de funcionários está disponível em `/funcionarios/novo/` para usuários com perfil Administrador.

O arquivo `.env` não é carregado automaticamente pelo Django. Exporte as variáveis no terminal antes de iniciar, por exemplo `export TIME_ZONE=America/Sao_Paulo`. Em desenvolvimento, os padrões permitem iniciar sem `.env`; nunca use a chave padrão em produção.

## Publicar na internet (Render)

O arquivo `render.yaml` descreve um serviço web Django e um PostgreSQL. O Render fornece HTTPS, `SECRET_KEY` é gerada pela plataforma, os arquivos estáticos são servidos pelo WhiteNoise e as migrations rodam ao iniciar o serviço. O domínio público só será criado depois de conectar e publicar o repositório.

1. Crie um repositório privado no GitHub para este projeto.
2. No terminal do projeto, publique o código (substitua a URL pela URL do seu repositório):

	```sh
	git add .
	git commit -m "Preparar aplicação LPZ Ponto"
	git branch -M main
	git remote add origin https://github.com/SEU-USUARIO/SEU-REPOSITORIO.git
	git push -u origin main
	```

3. Entre em Render usando sua conta GitHub, escolha **New → Blueprint**, conecte o repositório e aplique o `render.yaml`.
4. Aguarde o serviço web e o banco PostgreSQL ficarem disponíveis. O endereço público aparecerá no painel do serviço.
5. No painel do serviço web, abra o **Shell** e crie o administrador da produção:

	```sh
	python manage.py createsuperuser --username admin
	```

	Crie as contas de produção com senhas próprias. Usuários e dados do SQLite local, inclusive os de demonstração, não são enviados ao PostgreSQL automaticamente.

O Render pode exigir confirmação de cobrança ou plano pago, conforme os limites atuais da plataforma. Para uso real, configure backups do banco e política de retenção de dados; não use os usuários de demonstração em produção. A URL e o deploy não existem até concluir esses passos.

Para outra hospedagem, configure `DEBUG=False`, `SECRET_KEY` aleatória, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` e `DATABASE_URL` PostgreSQL com TLS. A configuração de produção força HTTPS, cookies seguros e HSTS.

Faça backups automatizados e teste a restauração do PostgreSQL. Defina política de retenção e acesso restrito antes de usar dados reais, especialmente coordenadas e dados pessoais (LGPD). Em ambiente de demonstração, use dados fictícios claramente identificados.

## Testes e comandos úteis

```sh
python manage.py check
python manage.py makemigrations
python manage.py migrate
python manage.py test
```

As migrations devem ser versionadas junto do código. O primeiro conjunto de testes cobre sequência de marcações, duração, inativação e isolamento do histórico. Solicitações/aprovações de correção, relatórios CSV, gráficos analíticos e fluxos completos de RH ainda não fazem parte desta etapa.