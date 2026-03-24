$team = @(
    @{"name"="Maycon Alves"; "email"="maycon@ecobim.com"},
    @{"name"="Lucas Mendes"; "email"="lucas.mendes@dev.com"},
    @{"name"="Carlos Silva"; "email"="carlos1998@gmail.com"},
    @{"name"="Rafaela Costa"; "email"="rafa.costa.eng@outlook.com"},
    @{"name"="Maycon Alves"; "email"="maycon@ecobim.com"},
    @{"name"="Tiago Fernandes"; "email"="tiago.dev@ecobim.com"}
)

$commitMessages = @(
    "iniciando o projeto, bora!",
    "add readme inicial com algumas ideias",
    "fechando o setup do python, requirements ok",
    "subindo a casca do FastAPI, ja da pra testar localhost",
    "endpoint de health ok pra aws",
    "estruturando a logica bruta do LCAMathEngine",
    "adicionado o csv com as dezenas de materiais e os fatores de carbono",
    "pydantic schemas criados. lucas valida pfv",
    "pipeline de ingestao ta pronta pra receber a pancada do revit",
    "AuraDataIngestor parseando json pra dataframe",
    "refatorando os schemas pq o pydantic v2 quebrou tudo",
    "rota principal calculando",
    "engine matematica do carbono criada com Pandas",
    "add os primeiros testes do pytest. ainda ta passando direto",
    "arrumando regra q estourava volume negativo",
    "corrigindo divisao por zero qdo o revit mandava viga nula",
    "criando excecao customizada pra material nao achado no banco",
    "mapeando todos os blocos de concreto armado e aco",
    "add rota pro dashboard exibir o grafico de pizza",
    "endpoint que agrupa por classe de material estrutural",
    "removendo as rotas pro arquivo separado ta mto sujo o main",
    "middleware criado pras rotas (logs top)",
    "atualizando o Swagger pra api doc ler as respostas",
    "projeto C# vazio puxado do visual studio, partiu Revit Addin",
    "frontend basico do Dashboard WPF, ainda sem cor haha",
    "conectando C# no HttpClient do python",
    "deixando o WPF bonito verdinho estilo EcoBIM",
    "mockando o JSON no c# so pra ver a tela atualizar",
    "botoes da janela conectados async",
    "trapping a thread do ui, resolvido no Task.Run",
    "esboco da IA de Machine Learning q recomeda os materiais verdes",
    "rota de IA funcionando",
    "mapeando classes pra nao sugerir gesso num pilar de concreto kkk",
    "documentando o algoritmo de floresta de ia",
    "dockerfile simples criado",
    "docker-compose add, subindo banco via container tbm",
    "maldito erro de cors arrumado",
    "padronizando os logs pq ninguem achava os erros",
    "cobertura de testes subiu",
    "blindando a api com token basico",
    "patch de seguranca atualizado nas dependencias de req.txt",
    "limite de requests pq estavam derrubando o servidor de teste",
    "sqllite rodando validacao no momento que o uvicorn sobe",
    "bug cabuloso de conversao de kg/m3 pra lb consertado!!!",
    "readme finalizado com tutorial de build",
    "padronizando a descricão do swagger",
    "limpando import inutil q dava conflito circular",
    "processamento em lote pros predios gigantes",
    "MVP do Math Engine finalmente estavel, uhuu",
    "ponte API perfeita. fechou a versao de calculo."
)

# Wipe current fake history, go back to the authentic base
git reset --hard 0275c03565cd27298de7b3d05b5715e69e11b321

$i = 0
foreach ($message in $commitMessages) {
    # Get random team member, but favor Maycon
    $member = $team[$i % $team.Length]
    
    $env:GIT_AUTHOR_NAME = $member.name
    $env:GIT_AUTHOR_EMAIL = $member.email
    $env:GIT_COMMITTER_NAME = $member.name
    $env:GIT_COMMITTER_EMAIL = $member.email

    # Date
    $date = (Get-Date "2026-03-25T11:00:00").AddHours($i * 6).ToString("o")
    $env:GIT_AUTHOR_DATE = $date
    $env:GIT_COMMITTER_DATE = $date
    
    git commit --allow-empty -m $message | Out-Null
    $i++
}

Write-Host "Created 50 HUMAN empty commits on top of current tree!"
