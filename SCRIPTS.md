# Scripts

## extrai_ementas_do_ppc.py

Gera o arquivo `disciplinas.json` a partir do arquivo
`ppc-2023.pdf`, contendo o PPC versão 2023. Requer o uso do
ambiente virtual descrito abaixo. Para executar o script e gerar
o arquivo `disciplinas.json` contendo apenas o conteúdo no PPC
(versão PDF) ative o
ambiente e execute o comando abaixo:

```
python bin/extrai_ementas_do_ppc.py --ppc docs/ppc-2023.pdf
```

> IMPORTANTE: O arquivo disciplinas.json criado é apenas o
> arquivo básico. O arquivo `dados/disciplinas.json` é o mantido
> manualmente (que originalmente foi criado com esse script), com
> a correção dos eventuais erros e adição de dados que não
> constam no PPC.

## Ambiente Virtual

Para usar o script, crie um ambiente virtual e instale os pacotes
indicados em `bin/requirements.txt`, com os comandos abaixo:

```
python3 -m venv venv
source venv/bin/activate
pip install -r bin/requirements.txt
````
