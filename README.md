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
python manage.py runserver
```

Acesse `http://127.0.0.1:8000/` e use os códigos `DEVELOPER_ACCESS_CODE` e `EMPLOYEE_ACCESS_CODE` definidos no ambiente. O código de desenvolvedor cria e autentica o superusuário `DEVELOPER_USERNAME` (padrão `admin`) e libera `/admin/`; o código de funcionário abre o totem `/totem/`. Em **Administração**, crie a conta do usuário e depois associe os dados e a foto facial em `/funcionarios/novo/`.

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
5. Configure `DEVELOPER_ACCESS_CODE` e `EMPLOYEE_ACCESS_CODE` nas variáveis privadas do serviço Render. Use códigos longos e diferentes; não os coloque no repositório. O primeiro cria/acessa o superusuário `admin`; o segundo libera o totem para registro de ponto por reconhecimento facial. Usuários e dados do SQLite local, inclusive os de demonstração, não são enviados ao PostgreSQL automaticamente.

O Render pode exigir confirmação de cobrança ou plano pago, conforme os limites atuais da plataforma. Para uso real, configure backups do banco e política de retenção de dados; não use os usuários de demonstração em produção. A URL e o deploy não existem até concluir esses passos.

Para outra hospedagem, configure `DEBUG=False`, `SECRET_KEY` aleatória, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` e `DATABASE_URL` PostgreSQL com TLS. A configuração de produção força HTTPS, cookies seguros e HSTS.

Faça backups automatizados e teste a restauração do PostgreSQL. Defina política de retenção e acesso restrito antes de usar dados reais, especialmente coordenadas e dados pessoais (LGPD). Em ambiente de demonstração, use dados fictícios claramente identificados.

## Reconhecimento facial

O totem `/totem/` usa a câmera e envia a foto como `multipart/form-data` ao endpoint `POST /totem/registrar-facial/` (`foto`, `kind` e campos de localização). O servidor compara o rosto com os perfis faciais dos funcionários ativos e só registra quando encontra uma correspondência única. As imagens capturadas para registrar ponto não são armazenadas. A foto enviada no cadastro é reduzida, convertida para JPEG e guardada em Base64 no campo `foto_base64`; o vetor facial fica no campo `face_encoding` do mesmo `EmployeeFaceProfile`. Administradores podem visualizar a foto na lista de funcionários.

Para cadastrar um funcionário, crie primeiro sua conta de acesso em **Administração → Usuários** e depois associe os dados do funcionário em `/funcionarios/novo/`, incluindo uma foto facial. A foto precisa mostrar exatamente um rosto e ter no máximo 5 MB. No totem, o código compartilhado libera a tela de marcação, e o rosto identifica a pessoa. A biometria é comparada com os perfis cadastrados; não há detecção de vivacidade, portanto fotos podem ser usadas para tentar falsificar uma identidade. Use somente em ambiente controlado e avalie uma solução com detecção de vivacidade e revisão de privacidade antes do uso real.

O reconhecimento requer `dlib-bin`, os modelos faciais, NumPy e Pillow; essas dependências estão listadas em `requirements.txt`. Se a instalação das dependências for interrompida, execute novamente `python -m pip install -r requirements.txt` no ambiente virtual ativo. Sem as dependências faciais, o sistema informa a indisponibilidade e não registra o ponto.

Use `python manage.py runserver` para iniciar a aplicação. A câmera do navegador requer `localhost` ou HTTPS e autorização explícita do usuário.

## Testes e comandos úteis

```sh
python manage.py check
python manage.py makemigrations
python manage.py migrate
python manage.py test
```

As migrations devem ser versionadas junto do código. O primeiro conjunto de testes cobre sequência de marcações, duração, inativação e isolamento do histórico. Solicitações/aprovações de correção, relatórios CSV, gráficos analíticos e fluxos completos de RH ainda não fazem parte desta etapa.