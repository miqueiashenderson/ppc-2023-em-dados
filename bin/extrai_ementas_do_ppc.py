import argparse
import json
import os
import re
from difflib import SequenceMatcher

import pdfplumber

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "..", "dados", "disciplinas.json")

REGEX1 = r"\d+\s+Ciência da Computação\s*–\s*UASC/UFCG\s*–\s*Projeto Pedagógico"
REGEX2 = r"Ciência da Computação\s*–\s*UASC/UFCG\s*–\s*Projeto Pedagógico\s*\d*"
REGEX3 = r"Ciência da Computação\s*–\s*UASC/UFCG\s*–\s*Projeto Pedagógico"

TRUNCAMENTOS_COMUNS = {
    "Impl": "Implementação",
    "Algor": "Algorithms",
    "Arq": "Architecture",
    "Aut": "Automatic",
    "Conhec": "Conhecimento",
    "Desc": "Descritiva",
    "Estat": "Estatística",
    "Fund": "Fundamentos",
    "Ger": "Gerenciamento",
    "Inter": "Internet",
    "Intro": "Introdução",
    "Ling": "Linguagem",
    "Mat": "Matemática",
    "Org": "Organização",
    "Padr": "Padrões",
    "Proc": "Processamento",
    "Prog": "Programação",
    "Red": "Redes",
    "Sist": "Sistemas",
    "Soft": "Software",
    "Tel": "Telecomunicações",
    "Ver": "Verificação",
}

REGEX_SECAO = r"^[A-Z]\.\s+Componentes?\s+Curriculares?\s+\S+.*$"


def limpa_texto(texto):
    if not texto:
        return None

    for regex in (REGEX1, REGEX2, REGEX3):
        texto = re.sub(regex, "", texto, flags=re.IGNORECASE)

    texto = re.sub(REGEX_SECAO, "", texto, flags=re.MULTILINE)

    return " ".join(texto.split())


def extrai_texto_do_apendice(pdf_path):
    texto = []
    with pdfplumber.open(pdf_path) as pdf:
        IDX_PAGINA_INICIAL_DAS_EMENTAS = 41
        for page in pdf.pages[IDX_PAGINA_INICIAL_DAS_EMENTAS:]:
            page_text = page.extract_text() or ""
            texto.append(page_text)

    return "\n".join(texto)


def separa_blocos_de_disciplinas(texto):
    """
    Divide o texto em blocos por disciplina.
    """
    pattern = r"\n(?=COMPONENTE CURRICULAR)"
    blocos = re.split(pattern, texto)

    return [b.strip() for b in blocos if "COMPONENTE CURRICULAR" in b]


def extrai_campo_raw(bloco, campo, outros_campos):
    """
    Extrai conteúdo bruto após um campo até o próximo campo conhecido.
    """
    fn_esc = re.escape(campo)
    others = [re.escape(f) + r"\s*:" for f in outros_campos if f != campo]

    pattern = rf"{fn_esc}\s*:\s*(.*?)\s*(?=" + "|".join(others) + r"|$)"
    match = re.search(pattern, bloco, re.DOTALL | re.IGNORECASE)

    if match:
        return match.group(1).strip()

    return None


def parse_pre_reqs(texto):
    if not texto:
        return []

    texto = re.sub(r"^\([a-zçãõéêíóú]+\)\s*", "", texto, flags=re.IGNORECASE)
    if (
        not texto
        or "nenhum" in texto.lower()
        or texto.lower() == "não há"
        or texto.lower() == "nao ha"
    ):
        return []

    # separa por vírgula ou quebra de linha
    partes = re.split(r",|\n", texto)
    return [
        p.strip()
        for p in partes
        if p.strip() and len(p.strip()) > 1
    ]


def parse_bibliografia(texto_raw):
    if not texto_raw:
        return []

    items = re.split(r"\n(?=\d+\.\s)", texto_raw)
    result = []
    for item in items:
        item_limpo = limpa_texto(item)
        if item_limpo and len(item_limpo) > 5:
            result.append(item_limpo)
    return result


def resolve_nome_prereq(nome_raw, nomes_conhecidos):
    """
    Resolve o nome bruto de um pré-requisito para o nome conhecido mais próximo.
    """
    nome_lower = nome_raw.lower().strip()
    if nome_lower in [n.lower() for n in nomes_conhecidos]:
        for n in nomes_conhecidos:
            if n.lower() == nome_lower:
                return n

    melhor_score = 0
    melhor_nome = None
    for n in nomes_conhecidos:
        score = SequenceMatcher(None, nome_lower, n.lower()).ratio()
        if score > melhor_score:
            melhor_score = score
            melhor_nome = n

    if melhor_score >= 0.6:
        return melhor_nome

    return nome_raw


def completa_truncamento(nome):
    """
    Completa nomes truncados usando o mapeamento TRUNCAMENTOS_COMUNS.
    """
    if not nome or len(nome) > 20:
        return nome
    partes = nome.split()
    resultado = []
    for p in partes:
        if p in TRUNCAMENTOS_COMUNS:
            resultado.append(TRUNCAMENTOS_COMUNS[p])
        else:
            resultado.append(p)
    return " ".join(resultado)


def separa_pre_coreq(texto):
    """
    Separa o texto de pré-requisitos do texto de co-requisitos.
    """
    if not texto:
        return "", ""
    parts = re.split(r"\bCO-REQUISITO\b[:\s]*", texto, flags=re.IGNORECASE)
    pre = parts[0].strip()
    coreq = parts[1].strip() if len(parts) > 1 else ""
    return pre, coreq


def _limpa_marcadores_secao(texto):
    """
    Remove marcadores de seção do PDF (A., B., C.) que vazam para blocos de disciplinas.
    """
    return re.sub(
        r"^[A-Z]\.\s+(Componentes?\s+Curriculares?|Componente\s+Curricular\s+Complementar\s+Obrigatório)\b.*$",
        "",
        texto,
        flags=re.MULTILINE,
    )


def parse_disciplina(block, nomes_conhecidos):
    block = _limpa_marcadores_secao(block)
    linhas = [l.strip() for l in block.split("\n") if l.strip()]

    nome = None
    if linhas and linhas[0].startswith("COMPONENTE CURRICULAR:"):
        rem = linhas[0].replace("COMPONENTE CURRICULAR:", "").strip()
        if rem:
            nome = rem
        elif len(linhas) > 1:
            nome = linhas[1]

    campos = [
        "COMPONENTE CURRICULAR",
        "CARGA HORÁRIA",
        "UNIDADE ACADÊMICA RESPONSÁVEL",
        "EMENTA",
        "BIBLIOGRAFIA BÁSICA",
        "BIBLIOGRAFIA COMPLEMENTAR",
        "Componentes Curriculares Obrigatórios",
        "Componente Curricular Complementar Obrigatório",
        "Componentes Curriculares Optativos",
    ]

    carga_horaria = None
    creditos = None

    for idx, l in enumerate(linhas):
        if "CARGA HORÁRIA" in l.upper():
            if idx + 1 < len(linhas):
                cl = linhas[idx + 1]
                m_carga = re.search(r"(\d+)\s*horas", cl, re.IGNORECASE)
                if m_carga:
                    carga_horaria = int(m_carga.group(1))
                m_parts = re.findall(r"(\d+)", cl)
                if len(m_parts) >= 2:
                    creditos = int(m_parts[1])
            break

    m_prereq = re.search(
        r"\d+\s*horas?\s+\d+\s*(.*?)\s*UNIDADE ACADÊMICA RESPONSÁVEL",
        block,
        re.DOTALL | re.IGNORECASE,
    )
    prereq_text = None
    coreq_text = None
    if m_prereq:
        prereq_raw = " ".join(m_prereq.group(1).split())
        prereq_raw = prereq_raw.rstrip(":")
        prereq_text, coreq_text = separa_pre_coreq(prereq_raw)

    unidade_raw = extrai_campo_raw(block, "UNIDADE ACADÊMICA RESPONSÁVEL", campos)
    ementa_raw = extrai_campo_raw(block, "EMENTA", campos)
    bib_basica_raw = extrai_campo_raw(block, "BIBLIOGRAFIA BÁSICA", campos)
    bib_complementar_raw = extrai_campo_raw(block, "BIBLIOGRAFIA COMPLEMENTAR", campos)

    prereqs = parse_pre_reqs(prereq_text)
    prereqs = [completa_truncamento(p) for p in prereqs]
    prereqs = [resolve_nome_prereq(p, nomes_conhecidos) for p in prereqs]

    coreqs = parse_pre_reqs(coreq_text)
    coreqs = [completa_truncamento(c) for c in coreqs]
    coreqs = [resolve_nome_prereq(c, nomes_conhecidos) for c in coreqs]

    data = {
        "nome": limpa_texto(nome),
        "carga_horaria": carga_horaria,
        "creditos": creditos,
        "unidade_responsavel": limpa_texto(unidade_raw),
        "prerequisitos": prereqs,
        "corequisitos": coreqs,
        "ementa": limpa_texto(ementa_raw),
        "bibliografia_basica": parse_bibliografia(bib_basica_raw),
        "bibliografia_complementar": parse_bibliografia(bib_complementar_raw),
    }

    return data


def main():
    parser = argparse.ArgumentParser(description="Extrai ementas e disciplinas do PPC em PDF.")
    parser.add_argument("--ppc", required=True, help="Caminho para o arquivo PDF do PPC")
    args = parser.parse_args()

    print("Extraindo texto do PDF...")
    texto = extrai_texto_do_apendice(args.ppc)

    print("Separando disciplinas...")
    blocos_disciplinas = separa_blocos_de_disciplinas(texto)

    print(f"Encontradas {len(blocos_disciplinas)} blocos de disciplinas")

    nomes_conhecidos = []
    for bloco in blocos_disciplinas:
        linhas = [l.strip() for l in bloco.split("\n") if l.strip()]
        if linhas and linhas[0].startswith("COMPONENTE CURRICULAR:"):
            rem = linhas[0].replace("COMPONENTE CURRICULAR:", "").strip()
            if rem:
                nomes_conhecidos.append(limpa_texto(rem))
            elif len(linhas) > 1:
                nomes_conhecidos.append(limpa_texto(linhas[1]))

    disciplinas = []
    for bloco in blocos_disciplinas:
        d = parse_disciplina(bloco, nomes_conhecidos)
        if d["nome"]:  # filtro básico
            disciplinas.append(d)

    saida = os.path.abspath(OUTPUT_PATH)
    os.makedirs(os.path.dirname(saida), exist_ok=True)

    print(f"Salvando JSON com {len(disciplinas)} disciplinas...")
    with open(saida, "w", encoding="utf-8") as f:
        json.dump(disciplinas, f, ensure_ascii=False, indent=2)

    print(f"Arquivo gerado: {saida}")


if __name__ == "__main__":
    main()
