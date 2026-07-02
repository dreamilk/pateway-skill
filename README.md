# pateway-skill

Hermes skill for querying the PatewayAI dashboard API from the command line.

It can fetch:

- Account balance / available quota
- API key list, service modes, monthly usage
- 24h / 7d / 30d usage summaries
- Detailed usage logs
- Service modes and model support
- Supported models per API key

## Install as a Hermes skill

```bash
git clone https://github.com/dreamilk/pateway-skill.git
mkdir -p ~/.hermes/skills/devops/pateway-dashboard
cp -r pateway-skill/* ~/.hermes/skills/devops/pateway-dashboard/
```

Then load the skill in Hermes when needed:

```text
/skill pateway-dashboard
```

## Configure credentials

Do **not** commit credentials. Set them as environment variables:

```bash
export PATEWAY_EMAIL='your-email@example.com'
export PATEWAY_PASSWORD='your-password'
```

Optional:

```bash
export PATEWAY_API_BASE='https://web.pateway.ai/api/v1'
export PATEWAY_TOKEN_FILE="$HOME/.hermes/cache/pateway_token.json"
```

## Usage

```bash
python scripts/pateway_api.py balance
python scripts/pateway_api.py keys
python scripts/pateway_api.py usage 24h
python scripts/pateway_api.py logs --page 1 --size 20
python scripts/pateway_api.py modes
python scripts/pateway_api.py key-models
python scripts/pateway_api.py all
```

## Requirements

- Python 3.10+
- `cryptography`

Install dependency:

```bash
python -m pip install cryptography
```

## Security

- The script reads `PATEWAY_EMAIL` and `PATEWAY_PASSWORD` from the environment.
- Login token is cached locally at `~/.hermes/cache/pateway_token.json` by default with mode `0600`.
- Never commit real credentials or cached tokens.
