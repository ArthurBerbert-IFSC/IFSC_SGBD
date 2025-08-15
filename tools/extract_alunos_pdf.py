import os
import re
import json
import unicodedata
from typing import List, Dict, Optional

import pdfplumber  # dependência obrigatória agora

HEADER_MATR_PAT = re.compile(r'matr', re.IGNORECASE)
HEADER_NOME_PAT = re.compile(r'nome', re.IGNORECASE)
MATRICULA_PAT = re.compile(r'\d{4,}')  # ajuste se necessário (ex: \d{6})

def normalize_text(s: Optional[str]) -> str:
    if not s:
        return ''
    s = s.strip()
    # Remover caracteres de controle
    s = re.sub(r'\s+', ' ', s)
    return s

def strip_accents(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

def detect_header_indices(rows: List[List[str]]):
    # Aumentado de 5 para 15 linhas iniciais para localizar cabeçalhos que podem
    # aparecer mais abaixo devido a logos, títulos ou legendas no topo.
    for i, row in enumerate(rows[:15]):  # olhar primeiras linhas (expandido)
        cleaned = [normalize_text(c).lower() for c in row]
        for j, cell in enumerate(cleaned):
            if HEADER_MATR_PAT.search(cell):
                # procurar nome
                for k, cell2 in enumerate(cleaned):
                    if HEADER_NOME_PAT.search(cell2):
                        return i, j, k
    return None

def extract_from_tables(page) -> List[Dict[str, str]]:
    tables = page.extract_tables() or []
    results = []
    for tbl in tables:
        # Normalizar (algumas libs retornam None)
        rows = [[normalize_text(c) for c in row] for row in tbl if any(normalize_text(c) for c in row)]
        if not rows:
            continue
        header_info = detect_header_indices(rows)
        if not header_info:
            continue
        header_row_idx, mat_idx, nome_idx = header_info
        for r in rows[header_row_idx+1:]:
            if mat_idx >= len(r) or nome_idx >= len(r):
                continue
            matricula_raw = normalize_text(r[mat_idx])
            nome_raw = normalize_text(r[nome_idx])
            if not matricula_raw or not nome_raw:
                continue
            if not MATRICULA_PAT.search(matricula_raw):
                continue
            matricula = re.sub(r'\D', '', matricula_raw)
            if not matricula:
                continue
            results.append({
                "matricula": matricula,
                "nome": nome_raw
            })
        if results:
            break  # já extraímos de uma tabela válida
    return results

def fallback_extract_text(page) -> List[Dict[str, str]]:
    text = page.extract_text() or ""
    lines = [l for l in (line.strip() for line in text.splitlines()) if l]
    results = []
    for line in lines:
        # Ex: 20231234 João da Silva
        m = re.match(r'^(\d{4,})\s+(.+)$', line)
        if m:
            matricula = m.group(1)
            nome = m.group(2).strip()
            # Heurística: evitar linha que seja só cabeçalho
            if HEADER_NOME_PAT.search(nome.lower()):
                continue
            results.append({"matricula": matricula, "nome": nome})
    return results

def extract_alunos_from_pdf(pdf_path: str) -> List[Dict[str, str]]:
    """Extrai alunos de um PDF usando pdfplumber se disponível; caso contrário tenta
    um fallback simples baseado em extração de texto linha a linha.
    """
    alunos: List[Dict[str, str]] = []
    with pdfplumber.open(pdf_path) as pdf:  # type: ignore
        if pdf.pages:
            first = pdf.pages[0]
            alunos = extract_from_tables(first)
            if not alunos:
                alunos = fallback_extract_text(first)
    # Deduplicação
    seen = set(); dedup = []
    for a in alunos:
        key = (a['matricula'], strip_accents(a['nome'].lower()))
        if key not in seen:
            seen.add(key)
            dedup.append(a)
    return dedup

def scan_folder(folder: str) -> Dict[str, List[Dict[str, str]]]:
    result = {}
    for root, _, files in os.walk(folder):
        for f in files:
            if f.lower().endswith('.pdf'):
                path = os.path.join(root, f)
                try:
                    alunos = extract_alunos_from_pdf(path)
                    result[path] = alunos
                except Exception as e:
                    result[path] = [{"erro": str(e)}]
    return result

def main():
    import argparse
    ap = argparse.ArgumentParser(description="Extrair alunos (matrícula, nome) da primeira página de PDFs.")
    ap.add_argument("entrada", help="Arquivo PDF ou pasta.")
    ap.add_argument("-o", "--out", help="Arquivo de saída (JSON). Se omitido, imprime.")
    args = ap.parse_args()

    if os.path.isdir(args.entrada):
        data = scan_folder(args.entrada)
    else:
        data = {args.entrada: extract_alunos_from_pdf(args.entrada)}

    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    else:
        print(json.dumps(data, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
