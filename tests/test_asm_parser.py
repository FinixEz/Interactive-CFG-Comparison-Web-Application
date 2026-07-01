import os

import pytest

from asm_parser import build_cfg_from_assembly, parse_assembly_file

GAS = """\
main:
    mov $1, %eax
    jmp end
loop1:
    add $1, %ebx
end:
    ret
"""


def test_gas_labels_and_unconditional_jump():
    G = build_cfg_from_assembly(GAS)
    assert {'main', 'loop1', 'end'} <= set(G.nodes())
    assert G.has_edge('main', 'end')        # jmp target
    assert not G.has_edge('main', 'loop1')  # unconditional jump: no fall-through
    assert G.has_edge('loop1', 'end')       # fall-through


COND = """\
a:
    cmp %eax, %ebx
    je c
b:
    nop
c:
    ret
"""


def test_conditional_jump_has_target_and_fallthrough():
    G = build_cfg_from_assembly(COND)
    assert G.has_edge('a', 'c')  # branch target
    assert G.has_edge('a', 'b')  # fall-through
    assert G.has_edge('b', 'c')  # plain fall-through


TASM = """\
start proc
    mov ax, 1
    jmp short done ; leave
foo label near
    inc bx
done label near
    ret
"""


def test_tasm_colonless_labels_and_size_qualifier():
    G = build_cfg_from_assembly(TASM)
    assert {'start', 'foo', 'done'} <= set(G.nodes())
    assert G.has_edge('start', 'done')      # 'short' qualifier skipped
    assert not G.has_edge('start', 'foo')   # jmp: no fall-through
    assert G.has_edge('foo', 'done')


TASM_COMMENT = """\
comment ;
junk_label label near
jmp done
;
real proc
    ret
"""


def test_tasm_comment_block_stripped_and_lines_preserved():
    G = build_cfg_from_assembly(TASM_COMMENT)
    assert 'junk_label' not in G.nodes()
    assert 'real' in G.nodes()
    # Blanked, not removed: 'real proc' must keep its original line number
    assert G.nodes['real'].get('start_line') == 4


def test_semicolon_comment_lines_do_not_break_jump_detection():
    asm = """\
a:
    jmp c
    ; trailing comment must not hide the jmp above
b:
    nop
c:
    ret
"""
    G = build_cfg_from_assembly(asm)
    assert G.has_edge('a', 'c')
    assert not G.has_edge('a', 'b')


def test_prelabel_code_gets_synthetic_entry_block():
    G = build_cfg_from_assembly("    nop\nlbl:\n    ret\n")
    assert 'entry' in G.nodes()
    assert G.has_edge('entry', 'lbl')


ANTHRAX = os.path.join(
    os.path.dirname(__file__), '..', 'Ghidra', 'theZoo',
    'Win32.Anthrax_Nov2008', 'Win32.Anthrax - Nov 2008', 'anthrax.asm')


@pytest.mark.skipif(not os.path.exists(ANTHRAX),
                    reason="theZoo sources not present (local-only regression)")
def test_anthrax_regression():
    G = parse_assembly_file(ANTHRAX)
    assert G.number_of_nodes() == 38
    assert G.number_of_edges() == 31
    # delta's block ends with "jmp exit_" but MASM appends unlabeled data
    # declarations (hello/GMK/where_to_go/vir_size) after it in the same
    # label-delimited block; the edge builder must look past those to find
    # the real terminating jump instead of a spurious fall-through.
    assert G.has_edge('delta', 'exit_')
    assert not G.has_edge('delta', 'infect')
