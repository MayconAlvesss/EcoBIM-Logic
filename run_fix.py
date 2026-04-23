import subprocess
import os

# Create a temporary file for the msg-filter
filter_script = """
import sys
mapping = {
    "Delete error": "fix: resolve execution errors",
    "fix: deploy script": "fix: update deployment script",
    "fix: polimento na doc": "docs: refine documentation",
    "fix: atualizando configs": "fix: update configuration files",
    "fix: removido prints perdidos": "fix: remove debug print statements",
    "fix: corrigindo bug de cast float": "fix: resolve float casting bug",
    "fix: arrumando cors": "fix: resolve CORS issues",
    "chore: clean up missed tracked files": "chore: clean up missed tracked files",
    "feat: mandando bala no C# Interface visual WPF!": "feat: implement C# WPF visual interface",
    "feat: ligando FastAPI no MathEngine perfeito!": "feat: integrate FastAPI with core MathEngine",
    "feat: separando rotas mocado": "feat: implement modularized mock routes",
    "feat: middleware mid feito": "feat: implement custom middleware",
    "feat: injecao de dependencias do fastapi": "feat: implement FastAPI dependency injection",
    "build: conteinerizando porque local dava mto erro": "build: containerize application to resolve local environment issues",
    "test: cobertura ta em 75, ta otimo ja": "test: achieve 75% test coverage",
    "feat: connectores e bridges prontas": "feat: complete connectors and bridges implementation",
    "test: uns notebooks que usei pra testar os dfs": "test: add research notebooks for dataframe validation",
    "feat: auth braba adicionada nas apis": "feat: implement robust API authentication",
    "feat: export reports pro json e csv": "feat: implement report export to JSON and CSV",
    "refactor: funcoes uteis pra logs": "refactor: implement utility functions for logging",
    "feat: pipeline do ingestion comecando a engrenar": "feat: implement data ingestion pipeline",
    "feat: machine learning pro recommender funcional": "feat: implement functional ML recommendation engine",
    "feat: coracao da matematica criada em pandas!!": "feat: implement core mathematical logic using Pandas",
    "feat: lca lifestyle skeleton": "feat: implement LCA lifecycle skeleton",
    "fix: excessoes mapeadas pra n quebrar": "fix: implement exception handling for stability",
    "feat: variaveis de ambiente e settings globais": "feat: implement environment variables and global settings",
    "build: requirements e lock de dependencias": "build: initialize requirements and dependency locking",
    "docs: add readme inicial com ideia do ecobim": "docs: add initial README with project vision"
}

msg = sys.stdin.read().strip()
new_msg = msg
found = False
for key, val in mapping.items():
    if key in msg:
        suffix = ""
        if " v" in msg:
            suffix = msg[msg.find(" v"):]
        new_msg = val + suffix
        found = True
        break
if not found:
    # Basic word translations for any leftover
    new_msg = new_msg.replace("corrigindo", "fixing").replace("arrumando", "fixing").replace("atualizando", "updating")

print(new_msg)
"""

with open("translate_msg.py", "w", encoding="utf-8") as f:
    f.write(filter_script)

# Configure git user
subprocess.run(["git", "config", "user.email", "mayconricardo2007@gmail.com"])
subprocess.run(["git", "config", "user.name", "Maycon Alves"])

# Execute git filter-branch
env = os.environ.copy()
env["FILTER_BRANCH_SQUELCH_WARNING"] = "1"

# Using python to run the script for each commit message
subprocess.run([
    "git", "filter-branch", "--force", "--msg-filter", "python ../translate_msg.py", "--", "--all"
], env=env)
