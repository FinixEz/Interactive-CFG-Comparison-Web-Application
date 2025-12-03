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
            # Match labels (e.g., "label:", ".LBB0_1:", "test:")
            if ':' in line and not line.startswith('#'):
                # Extract label name (everything before the colon)
                label_match = re.match(r'^([.\w]+):', line)
                if label_match:
                    label_name = label_match.group(1)
                    labels[label_name] = i
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
            
            # Skip empty lines and comments
            if not line_stripped or line_stripped.startswith('#'):
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
        
        for i, (block_id, block_info) in enumerate(basic_blocks.items()):
            lines = block_info['lines']
            if not lines:
                continue
            
            last_line = lines[-1].strip().lower()
            
            # Check for jump instructions
            has_unconditional_jump = False
            has_conditional_jump = False
            jump_target = None
            
            # Parse the last instruction
            parts = last_line.split()
            if parts:
                instruction = parts[0]
                
                # Check for unconditional jumps
                if instruction in self.jumps['unconditional']:
                    has_unconditional_jump = True
                    if instruction != 'ret' and instruction != 'retn' and len(parts) > 1:
                        jump_target = parts[1].rstrip(',')
                
                # Check for conditional jumps
                elif instruction in self.jumps['conditional']:
                    has_conditional_jump = True
                    if len(parts) > 1:
                        jump_target = parts[1].rstrip(',')
                
                # Check for calls (usually fall through)
                elif instruction in self.jumps['call']:
                    # Calls typically return, so add fall-through edge
                    if i + 1 < len(block_list):
                        next_block = block_list[i + 1]
                        G.add_edge(block_id, next_block)
            
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
            
            # Add fall-through edge for conditional jumps or if no jump
            if has_conditional_jump or (not has_unconditional_jump and instruction not in self.jumps['unconditional']):
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
