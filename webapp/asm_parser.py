"""
Assembly file parser for Control Flow Graph generation.

This module parses assembly files (.s, .asm) and generates NetworkX graphs
compatible with the existing CFG comparison logic.
"""

import re
import networkx as nx
from typing import Dict, List, Set, Tuple, Optional
import os


def preprocess_masm(asm_content: str, inc_dir: str = '.') -> str:
    """
    Expand INCLUDE directives like MASM does.
    
    This preprocessor handles MASM-style INCLUDE directives, which are common
    in malware samples (e.g., theZoo malware collection). It recursively expands
    all INCLUDE files, giving you the fully expanded assembly exactly as the
    assembler sees it.
    
    Args:
        asm_content: Assembly source code as string
        inc_dir: Directory to search for include files
        
    Returns:
        Expanded assembly code with all INCLUDE directives resolved
    """
    lines = asm_content.split('\n')
    expanded = []
    
    for line in lines:
        line_stripped = line.strip()
        
        # INCLUDE directive (case-insensitive)
        if line_stripped.upper().startswith('INCLUDE '):
            inc_file = line_stripped.split(' ', 1)[1].strip().strip('"\'')
            try:
                inc_path = os.path.join(inc_dir, inc_file)
                # Try multiple encodings for include files
                inc_content = None
                for encoding in ['utf-8', 'latin-1', 'cp1252']:
                    try:
                        with open(inc_path, 'r', encoding=encoding) as f:
                            inc_content = f.read()
                        break
                    except (UnicodeDecodeError, FileNotFoundError):
                        continue
                
                if inc_content:
                    # Recursively expand includes in the included file
                    inc_expanded = preprocess_masm(inc_content, inc_dir)
                    expanded.extend(inc_expanded.split('\n'))
                    print(f"✓ Expanded INCLUDE: {inc_file}")
                else:
                    print(f"⚠ WARNING: Could not read {inc_file}")
                    expanded.append(line)  # Keep original line if include fails
            except Exception as e:
                print(f"⚠ WARNING: Error processing {inc_file}: {e}")
                expanded.append(line)  # Keep original line if include fails
        else:
            expanded.append(line)
    
    return '\n'.join(expanded)


class AssemblyParser:
    """Parser for assembly code to extract control flow graphs."""
    
    # Jump instructions for different architectures
    JUMP_INSTRUCTIONS = {
        'x86_64': {
            'unconditional': {'jmp', 'ret', 'retn'},
            'conditional': {'je', 'jne', 'jz', 'jnz', 'jg', 'jge', 'jl', 'jle', 
                          'ja', 'jae', 'jb', 'jbe', 'jo', 'jno', 'js', 'jns',
                          'jp', 'jpe', 'jnp', 'jpo', 'jcxz', 'jecxz'},
            'call': {'call'},
        },
        'arm64': {
            'unconditional': {'b', 'br', 'ret'},
            'conditional': {'b.eq', 'b.ne', 'b.cs', 'b.cc', 'b.mi', 'b.pl',
                          'b.vs', 'b.vc', 'b.hi', 'b.ls', 'b.ge', 'b.lt',
                          'b.gt', 'b.le', 'cbz', 'cbnz', 'tbz', 'tbnz'},
            'call': {'bl', 'blr'},
        }
    }
    
    def __init__(self, arch: str = 'x86_64'):
        """
        Initialize the assembly parser.
        
        Args:
            arch: Target architecture ('x86_64' or 'arm64')
        """
        self.arch = arch
        self.jumps = self.JUMP_INSTRUCTIONS.get(arch, self.JUMP_INSTRUCTIONS['x86_64'])
        
    def detect_architecture(self, asm_code: str) -> str:
        """
        Auto-detect architecture from assembly code.
        
        Args:
            asm_code: Assembly code as string
            
        Returns:
            Detected architecture ('x86_64' or 'arm64')
        """
        # Simple heuristic: look for architecture-specific instructions
        asm_lower = asm_code.lower()
        
        # ARM64 indicators
        arm_indicators = ['adrp', 'stp', 'ldp', 'b.eq', 'b.ne', 'cbz', 'cbnz']
        # x86_64 indicators
        x86_indicators = ['mov\t', 'push', 'pop', 'rax', 'rbx', 'rcx', 'rdx', 'rsp', 'rbp']
        
        arm_score = sum(1 for ind in arm_indicators if ind in asm_lower)
        x86_score = sum(1 for ind in x86_indicators if ind in asm_lower)
        
        return 'arm64' if arm_score > x86_score else 'x86_64'
    
    def parse_assembly_file(self, filepath: str, auto_detect_arch: bool = True) -> nx.DiGraph:
        """
        Parse an assembly file and generate a control flow graph.
        
        Args:
            filepath: Path to assembly file
            auto_detect_arch: Whether to auto-detect architecture
            
        Returns:
            NetworkX directed graph representing the CFG
        """
        # Try reading with different encodings
        encodings = ['utf-8', 'latin-1', 'cp1252']
        asm_code = None
        
        for encoding in encodings:
            try:
                with open(filepath, 'r', encoding=encoding) as f:
                    asm_code = f.read()
                break
            except UnicodeDecodeError:
                continue
                
        if asm_code is None:
            # If all fail, read as binary and decode with replacement
            with open(filepath, 'rb') as f:
                asm_code = f.read().decode('utf-8', errors='replace')
        
        # Preprocess MASM INCLUDE directives for .asm files
        if filepath.lower().endswith('.asm'):
            inc_dir = os.path.dirname(filepath) or '.'
            asm_code = preprocess_masm(asm_code, inc_dir)
            print(f"✓ Preprocessed MASM file: {filepath}")
        
        if auto_detect_arch:
            self.arch = self.detect_architecture(asm_code)
            self.jumps = self.JUMP_INSTRUCTIONS.get(self.arch, self.JUMP_INSTRUCTIONS['x86_64'])
        
        return self.build_cfg_from_assembly(asm_code)
    
    def build_cfg_from_assembly(self, asm_code: str) -> nx.DiGraph:
        """
        Build a control flow graph from assembly code.
        
        Args:
            asm_code: Assembly code as string
            
        Returns:
            NetworkX directed graph
        """
        lines = asm_code.split('\n')

        # Blank out TASM `comment` block comments (keeps line numbering intact
        # so the inspector's line highlighting stays aligned)
        lines = self._strip_comment_blocks(lines)

        # Extract labels and their line numbers
        labels = self._extract_labels(lines)
        
        # Build basic blocks
        basic_blocks = self._build_basic_blocks(lines, labels)
        
        # Create graph
        G = nx.DiGraph()
        
        # Add nodes for each basic block
        for block_id, block_info in basic_blocks.items():
            G.add_node(block_id, **block_info)
        
        # Add edges based on control flow
        self._add_control_flow_edges(G, basic_blocks, labels)
        
        return G
    
    def _strip_comment_blocks(self, lines: List[str]) -> List[str]:
        """
        Blank out TASM/MASM ``comment`` block comments.

        The directive ``comment <delim>`` starts a block that runs until the
        delimiter character appears again (e.g. ``comment ;) ... (;``). These
        blocks are common in real malware headers (theZoo's RELOCK.ASM opens
        with one). Lines are replaced with '' rather than removed so that line
        numbers stay aligned with the displayed source.
        """
        out = list(lines)
        i, n = 0, len(lines)
        while i < n:
            m = re.match(r'^comment\b\s*(\S)', lines[i].strip(), re.IGNORECASE)
            if not m:
                i += 1
                continue
            delim = m.group(1)
            opening_rest = lines[i].strip()[m.end():]
            out[i] = ''
            i += 1
            # Closing delimiter may already be on the opening line
            if delim in opening_rest:
                continue
            while i < n:
                closes = delim in lines[i]
                out[i] = ''
                i += 1
                if closes:
                    break
        return out

    def _extract_labels(self, lines: List[str]) -> Dict[str, int]:
        """
        Extract all labels and their line numbers from assembly code.

        Args:
            lines: List of assembly code lines

        Returns:
            Dictionary mapping label names to line numbers
        """
        labels = {}
        for i, line in enumerate(lines):
            line = line.strip()
            if not line or line.startswith('#') or line.startswith(';'):
                continue
            # Colon labels (GAS/MASM): "label:", ".LBB0_1:", "test:"
            colon_match = re.match(r'^([.\w]+):', line)
            if colon_match:
                labels[colon_match.group(1)] = i
                continue
            # Colon-less TASM/MASM labels: "name label near", "name proc".
            # All of RELOCK.ASM's code labels use this form.
            directive_match = re.match(r'^([.\w$]+)\s+(label|proc)\b', line, re.IGNORECASE)
            if directive_match:
                labels[directive_match.group(1)] = i
        return labels
    
    def _build_basic_blocks(self, lines: List[str], labels: Dict[str, int]) -> Dict[str, dict]:
        """
        Build basic blocks from assembly lines.
        
        Args:
            lines: List of assembly code lines
            labels: Dictionary of labels and their line numbers
            
        Returns:
            Dictionary of basic blocks with metadata
        """
        basic_blocks = {}
        current_block_id = None
        current_block_lines = []
        current_block_start = 0
        
        label_lines = set(labels.values())
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Skip empty lines and comments ('#' GAS style, ';' MASM/NASM style)
            if not line_stripped or line_stripped.startswith('#') or line_stripped.startswith(';'):
                continue
            
            # Check if this line is a label (start of new block)
            if i in label_lines:
                # Save previous block if exists
                if current_block_id is not None and current_block_lines:
                    basic_blocks[current_block_id] = {
                        'lines': current_block_lines.copy(),
                        'start_line': current_block_start,
                        'end_line': i - 1
                    }
                
                # Start new block
                label_name = None
                for lbl, line_num in labels.items():
                    if line_num == i:
                        label_name = lbl
                        break
                
                current_block_id = label_name or f"block_{i}"
                current_block_lines = [line_stripped]
                current_block_start = i
            else:
                # Add line to current block
                if current_block_id is None:
                    # Create initial block if we haven't seen a label yet
                    current_block_id = "entry"
                    current_block_start = i
                    current_block_lines = []
                
                current_block_lines.append(line_stripped)
        
        # Save last block
        if current_block_id is not None and current_block_lines:
            basic_blocks[current_block_id] = {
                'lines': current_block_lines.copy(),
                'start_line': current_block_start,
                'end_line': len(lines) - 1
            }
        
        return basic_blocks
    
    def _add_control_flow_edges(self, G: nx.DiGraph, basic_blocks: Dict[str, dict], 
                                labels: Dict[str, int]) -> None:
        """
        Add control flow edges to the graph based on jump instructions.
        
        Args:
            G: NetworkX graph to add edges to
            basic_blocks: Dictionary of basic blocks
            labels: Dictionary of labels
        """
        block_list = list(basic_blocks.keys())

        def _clean(raw: str) -> str:
            # Strip inline comments (';' MASM/NASM, '#' GAS) and a leading
            # "label:" prefix so only the instruction itself is parsed
            cleaned = raw.strip().lower()
            cleaned = cleaned.split(';', 1)[0].split('#', 1)[0].strip()
            return re.sub(r'^[.\w]+:\s*', '', cleaned)

        for i, (block_id, block_info) in enumerate(basic_blocks.items()):
            lines = block_info['lines']
            if not lines:
                continue

            # Scan backward for the last actual control-flow instruction.
            # Trailing unlabeled data declarations (e.g. "hello db ...",
            # common right after a MASM/TASM jmp with no colon label) get
            # appended to this block by _build_basic_blocks and would
            # otherwise be mistaken for the block's terminating instruction,
            # silently dropping the real jump's edge.
            for raw in reversed(lines):
                cleaned = _clean(raw)
                if not cleaned:
                    continue
                mnemonic = cleaned.split()[0] if cleaned.split() else ''
                if mnemonic in self.jumps['unconditional'] or mnemonic in self.jumps['conditional']:
                    last_line = cleaned
                    break
            else:
                last_line = _clean(lines[-1])

            # Check for jump instructions
            has_unconditional_jump = False
            jump_target = None

            # Parse the last instruction
            parts = last_line.split()
            instruction = parts[0] if parts else ''

            # Skip MASM size/distance qualifiers to find the real target operand
            QUALIFIERS = {'short', 'near', 'far', 'ptr', 'dword', 'word', 'byte'}
            operands = [p.rstrip(',') for p in parts[1:] if p.rstrip(',') not in QUALIFIERS]

            # Check for unconditional jumps
            if instruction in self.jumps['unconditional']:
                has_unconditional_jump = True
                if instruction not in ('ret', 'retn') and operands:
                    jump_target = operands[0]

            # Check for conditional jumps (fall through handled below)
            elif instruction in self.jumps['conditional']:
                if operands:
                    jump_target = operands[0]

            # Add edge to jump target if it exists
            if jump_target:
                # Remove common prefixes/suffixes from jump targets
                jump_target = jump_target.strip()
                # Handle different jump target formats
                if jump_target.startswith('.'):
                    target_label = jump_target
                else:
                    target_label = jump_target.split('@')[0]  # Remove @PLT, @GOT, etc.

                if target_label in basic_blocks:
                    G.add_edge(block_id, target_label)

            # Fall-through edge for everything except unconditional jumps/returns
            # (conditional jumps and calls continue to the next block)
            if not has_unconditional_jump:
                if i + 1 < len(block_list):
                    next_block = block_list[i + 1]
                    G.add_edge(block_id, next_block)


def parse_assembly_file(filepath: str, arch: str = 'x86_64', auto_detect: bool = True) -> nx.DiGraph:
    """
    Convenience function to parse an assembly file.
    
    Args:
        filepath: Path to assembly file
        arch: Target architecture (default: 'x86_64')
        auto_detect: Auto-detect architecture from code
        
    Returns:
        NetworkX directed graph representing the CFG
    """
    parser = AssemblyParser(arch)
    return parser.parse_assembly_file(filepath, auto_detect_arch=auto_detect)


def build_cfg_from_assembly(asm_code: str, arch: str = 'x86_64') -> nx.DiGraph:
    """
    Convenience function to build CFG from assembly code string.
    
    Args:
        asm_code: Assembly code as string
        arch: Target architecture (default: 'x86_64')
        
    Returns:
        NetworkX directed graph representing the CFG
    """
    parser = AssemblyParser(arch)
    return parser.build_cfg_from_assembly(asm_code)
