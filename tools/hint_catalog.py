#!/usr/bin/env python3
"""
hint_catalog.py - Write the operators' catalogue of every hint (server/HINTS.md).

    python3 tools/hint_catalog.py [OUT]          default: server/HINTS.md

Hint texts are fixed per stage and variant (they never contain a seed's
constants or answers), so one document covers every student. Answers and
seed-specific walkthroughs are NOT in it: for a particular student's bomb use
`bomblabctl solution <user> <bomb|practice|dN>`.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import bank  # noqa: E402

# What a stuck student on the scored bomb (no hints there) can practise.
CMU_DRILL = {"p1": "D0·1, D1", "p2": "D3", "p3": "D4", "p4": "D5·2",
             "p5": "D6·1", "p6": "D7", "secret": "D8·2 (풀기), D9 (찾기)"}


def stage_label(bomb, i):
    p = bomb.phases[i]
    if p.slot == "secret":
        return "숨은 단계"
    return "%d단계" % (i + 1) if bomb.kind != "cmu" else "phase %d" % (i + 1)


def section(kind, out):
    variants = bank.variants(kind)
    base = bank.build(kind, 1)
    out.append("## %s" % base.title)
    out.append("")
    for i, p in enumerate(base.phases):
        names = variants[p.slot]
        for name in names:
            v = bank.build(kind, 1, force={p.slot: name}).phases[i]
            label = stage_label(base, i)
            if len(names) > 1:
                label += " — 변형 `%s`" % name
            out.append("### %s · %s" % (label, v.title))
            out.append("")
            for k, h in enumerate(v.hints, 1):
                out.append("%d. %s" % (k, h))
            if kind == "cmu":
                out.append("")
                out.append("_과제형 `~/bomb`에서 이 phase로 막힌 학생 → 연습할 드릴: %s_"
                           % CMU_DRILL[p.slot])
            out.append("")


def main(argv):
    path = argv[1] if len(argv) > 1 else os.path.join(ROOT, "server", "HINTS.md")
    out = [
        "# 힌트 전체 목록 (운영진용)",
        "",
        "`tools/hint_catalog.py`가 생성한 문서입니다. 직접 고치지 말고, 힌트를 바꿨다면 다시 생성하세요.",
        "",
        "- 힌트는 **단계마다 3개**이고 1 → 2 → 3 순서로 점점 구체적입니다. 학생은 `bomblab hint <폭탄> <단계>`로 하나씩 엽니다.",
        "- 힌트 문장은 학생·시드와 상관없이 같습니다. **정답은 들어 있지 않습니다.**",
        "- 특정 학생 폭탄의 정답과 풀이는 `sudo bomblabctl solution <학생> <bomb|practice|d0..d9>`로 봅니다. 그 학생이 연 힌트도 함께 나옵니다.",
        "- 연습 폭탄(`~/practice`)과 과제형 폭탄(`~/bomb`)은 같은 CMU 구조 폭탄입니다. 아래 \"CMU 구조 폭탄\" 힌트는 **연습 폭탄에서만** 열립니다. 과제형에는 힌트·해설이 없습니다.",
        "",
        "---",
        "",
    ]
    for kind in bank.kinds():
        section(kind, out)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out).rstrip() + "\n")
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
