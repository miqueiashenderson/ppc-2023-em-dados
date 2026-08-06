import argparse
import json
import re

import pdfplumber


OUTPUT_PATH = "disciplinas.json"


REGEX1 = r"\d+\s+Ciência da Computação\s*–\s*UASC/UFCG\s*–\s*Projeto Pedagógico"
REGEX2 = r"Ciência da Computação\s*–\s*UASC/UFCG\s*–\s*Projeto Pedagógico\s*\d*"
REGEX3 = r"Ciência da Computação\s*–\s*UASC/UFCG\s*–\s*Projeto Pedagógico"

def limpa_texto(texto):
    if not texto:
        return None

    for regex in (REGEX1, REGEX2, REGEX3):
        texto = re.sub(regex, "", texto, flags=re.IGNORECASE)

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
    others = [re.escape(f) for f in outros_campos if f != campo]

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
        or "a depender da ementa" in texto.lower()
    ):
        return []

    # separa por vírgula, quebra de linha ou 'e'
    partes = re.split(r",|\n|\be\b", texto)
    return [
        p.strip()
        for p in partes
        if p.strip() and p.strip().lower() != "e" and len(p.strip()) > 1
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


def parse_disciplina(block):
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
    if m_prereq:
        prereq_raw = " ".join(m_prereq.group(1).split())
        prereq_text = prereq_raw.rstrip(":")

    unidade_raw = extrai_campo_raw(block, "UNIDADE ACADÊMICA RESPONSÁVEL", campos)
    ementa_raw = extrai_campo_raw(block, "EMENTA", campos)
    bib_basica_raw = extrai_campo_raw(block, "BIBLIOGRAFIA BÁSICA", campos)
    bib_complementar_raw = extrai_campo_raw(block, "BIBLIOGRAFIA COMPLEMENTAR", campos)

    data = {
        "nome": limpa_texto(nome),
        "carga_horaria": carga_horaria,
        "creditos": creditos,
        "unidade_responsavel": limpa_texto(unidade_raw),
        "prerequisitos": parse_pre_reqs(prereq_text),
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

    disciplinas = []
    for bloco in blocos_disciplinas:
        d = parse_disciplina(bloco)
        if d["nome"]:  # filtro básico
            disciplinas.append(d)

    print(f"Salvando JSON com {len(disciplinas)} disciplinas...")
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(disciplinas, f, ensure_ascii=False, indent=2)

    print(f"✅ Arquivo gerado: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
