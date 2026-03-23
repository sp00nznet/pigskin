#!/usr/bin/env python3
"""
Pigskin ROM Analyzer — M68K disassembly + function discovery + C code generation.

Reads a Genesis ROM, performs recursive-descent disassembly from known entry points,
discovers function boundaries via call graph + jump table scanning, and exports
a JSON function map for the code generator.

Usage:
    python tools/analyze_rom.py <rom_path> [--output functions.json] [--disasm] [--stats]
"""

import struct
import json
import sys
import os
from collections import defaultdict
from capstone import Cs, CS_ARCH_M68K, CS_MODE_M68K_000

# ============================================================
# ROM parsing
# ============================================================

class GenesisROM:
    def __init__(self, path):
        with open(path, 'rb') as f:
            self.data = f.read()
        self.size = len(self.data)
        self._parse_header()
        self._parse_vectors()

    def _parse_header(self):
        self.console = self.data[0x100:0x110].decode('ascii', errors='replace').strip()
        self.copyright = self.data[0x110:0x120].decode('ascii', errors='replace').strip()
        self.title_domestic = self.data[0x120:0x150].decode('ascii', errors='replace').strip()
        self.title_overseas = self.data[0x150:0x180].decode('ascii', errors='replace').strip()
        self.serial = self.data[0x180:0x18E].decode('ascii', errors='replace').strip()
        self.checksum = struct.unpack('>H', self.data[0x18E:0x190])[0]
        self.rom_start = struct.unpack('>I', self.data[0x1A0:0x1A4])[0]
        self.rom_end = struct.unpack('>I', self.data[0x1A4:0x1A8])[0]
        self.region = self.data[0x1F0:0x1F3].decode('ascii', errors='replace').strip()

    def _parse_vectors(self):
        self.initial_sp = struct.unpack('>I', self.data[0x00:0x04])[0]
        self.initial_pc = struct.unpack('>I', self.data[0x04:0x08])[0]
        self.vectors = {}
        vector_names = {
            2: 'bus_error', 3: 'address_error', 4: 'illegal_insn',
            5: 'div_zero', 6: 'chk', 7: 'trapv',
            8: 'privilege_violation', 9: 'trace',
            25: 'irq1', 26: 'irq2', 27: 'irq3',
            28: 'irq4', 29: 'irq5', 30: 'irq6_vblank', 31: 'irq7',
        }
        for idx, name in vector_names.items():
            addr = struct.unpack('>I', self.data[idx*4:(idx+1)*4])[0]
            if addr != 0 and addr < self.size:
                self.vectors[name] = addr

    def read8(self, addr):
        if addr < self.size:
            return self.data[addr]
        return 0

    def read16(self, addr):
        if addr + 1 < self.size:
            return struct.unpack('>H', self.data[addr:addr+2])[0]
        return 0

    def read32(self, addr):
        if addr + 3 < self.size:
            return struct.unpack('>I', self.data[addr:addr+4])[0]
        return 0

    def print_info(self):
        print(f"Title:     {self.title_domestic}")
        print(f"Copyright: {self.copyright}")
        print(f"Serial:    {self.serial}")
        print(f"ROM size:  {self.size} bytes ({self.size//1024} KB)")
        print(f"Entry PC:  ${self.initial_pc:06X}")
        print(f"Initial SP:${self.initial_sp:06X}")
        print(f"Checksum:  ${self.checksum:04X}")
        print(f"Region:    {self.region}")


# ============================================================
# Recursive descent disassembler + function finder
# ============================================================

class M68KAnalyzer:
    CALL_MNEMONICS = {'bsr', 'jsr'}
    UNCONDITIONAL_ENDS = {'bra', 'jmp', 'rts', 'rte', 'rtr'}
    BIT_MNEMONICS = {'btst', 'bset', 'bclr', 'bchg'}

    def __init__(self, rom):
        self.rom = rom
        self.cs = Cs(CS_ARCH_M68K, CS_MODE_M68K_000)
        self.cs.detail = True

        self.visited = set()
        self.instructions = {}          # addr -> (mnemonic, op_str, size, bytes)
        self.functions = {}             # addr -> dict
        self.call_graph = defaultdict(set)
        self.xrefs_to = defaultdict(set)
        self.labels = {}
        self.jump_tables = {}           # addr -> list of target addrs

    # Explicit seed addresses for functions not reachable by static analysis.
    # These are discovered through manual inspection of the ROM (indirect jumps,
    # PC-relative calls, computed addresses, etc.)
    EXPLICIT_SEEDS = {
        0x0E8FE0: "main_game_entry",     # JMP target from init (via register)
        0x0EAD36: "sub_0EAD36",          # Starts with RTS
        0x0FB294: "sub_0FB294",          # Starts with MOVEM, game logic
        0x0FB1C2: "sub_0FB1C2",          # Starts with MOVE.W, game logic
        # BSR/JSR targets not found by recursive descent
        0x0F8452: "sub_0F8452",
        0x0F970C: "sub_0F970C",
        0x0F9C9C: "sub_0F9C9C",
        0x0F9E2E: "sub_0F9E2E",
        0x0FA2D4: "sub_0FA2D4",
        0x0FA14A: "sub_0FA14A",
    }

    def analyze(self):
        """Run full analysis."""
        # Gather initial entry points
        entry_points = set()
        entry_points.add(self.rom.initial_pc)
        for name, addr in self.rom.vectors.items():
            entry_points.add(addr)
            self.labels[addr] = f"vec_{name}"
        self.labels[self.rom.initial_pc] = "entry_point"

        # Add explicit seeds for functions unreachable by recursive descent
        for addr, name in self.EXPLICIT_SEEDS.items():
            entry_points.add(addr)
            self.labels[addr] = name
        print(f"Added {len(self.EXPLICIT_SEEDS)} explicit seed functions")

        # Scan ROM for lea-based jump tables and inline address tables
        jt_targets = self._scan_jump_tables()
        entry_points.update(jt_targets)

        print(f"\nStarting analysis from {len(entry_points)} entry points "
              f"(vectors + {len(jt_targets)} jump table targets)...")

        # Multi-pass: disassemble, discover new targets, repeat
        all_func_entries = set(entry_points)
        work = list(entry_points)
        pass_num = 0

        while work:
            pass_num += 1
            new_work = []
            for addr in work:
                if addr in self.visited or addr >= self.rom.size or addr < 0x200:
                    continue
                if addr & 1:  # M68K requires even addresses
                    continue
                new_targets = self._disassemble_block(addr)
                for target, is_call in new_targets:
                    if target not in self.visited and 0x200 <= target < self.rom.size and not (target & 1):
                        new_work.append(target)
                        if is_call:
                            all_func_entries.add(target)
            work = new_work

        # Second pass: scan disassembled code for LEA/MOVE patterns that load addresses
        more_targets = self._scan_address_loads()
        if more_targets:
            print(f"  Found {len(more_targets)} additional targets from address-loading instructions")
            work = list(more_targets - self.visited)
            all_func_entries.update(more_targets)
            while work:
                new_work = []
                for addr in work:
                    if addr in self.visited or addr >= self.rom.size or addr < 0x200 or (addr & 1):
                        continue
                    new_targets = self._disassemble_block(addr)
                    for target, is_call in new_targets:
                        if target not in self.visited and 0x200 <= target < self.rom.size and not (target & 1):
                            new_work.append(target)
                            if is_call:
                                all_func_entries.add(target)
                work = new_work

        # Prologue scan: find LINK/MOVEM patterns in unvisited ROM
        prologue_targets = self._scan_prologues()
        if prologue_targets:
            print(f"  Found {len(prologue_targets)} prologue-pattern functions in unvisited ROM")
            work = list(prologue_targets - self.visited)
            all_func_entries.update(prologue_targets)
            while work:
                new_work = []
                for addr in work:
                    if addr in self.visited or addr >= self.rom.size or addr < 0x200 or (addr & 1):
                        continue
                    new_targets = self._disassemble_block(addr)
                    for target, is_call in new_targets:
                        if target not in self.visited and 0x200 <= target < self.rom.size and not (target & 1):
                            new_work.append(target)
                            if is_call:
                                all_func_entries.add(target)
                work = new_work

        # Build function map
        self._build_functions(all_func_entries)

        print(f"Disassembled {len(self.instructions)} instructions")
        print(f"Found {len(self.functions)} functions")
        print(f"Found {len(self.xrefs_to)} cross-references")

    def _scan_jump_tables(self):
        """Scan ROM for potential jump/address tables."""
        targets = set()
        rom = self.rom

        # Look for sequences of 3+ longword addresses pointing into ROM code area
        # (code area appears to be $0E8000+ based on entry point)
        i = 0x200
        while i < rom.size - 12:
            addrs = []
            j = i
            while j < rom.size - 3:
                val = struct.unpack('>I', rom.data[j:j+4])[0]
                if 0x200 <= val < rom.size and (val & 1) == 0:
                    addrs.append(val)
                    j += 4
                else:
                    break
            if len(addrs) >= 3:
                # Heuristic: tables within code area are more likely to be real
                code_range = sum(1 for a in addrs if a >= 0x0E0000)
                if code_range >= len(addrs) * 0.5:
                    self.jump_tables[i] = addrs
                    for a in addrs:
                        targets.add(a)
                        if a not in self.labels:
                            self.labels[a] = f"jt_{a:06X}"
                i = j
            else:
                i += 2

        print(f"Found {len(self.jump_tables)} jump tables with {len(targets)} unique targets")
        return targets

    def _scan_address_loads(self):
        """Scan disassembled code for LEA/MOVE.L #addr patterns that reference code."""
        targets = set()
        for addr, (mnemonic, op_str, size, raw) in self.instructions.items():
            if mnemonic in ('lea', 'pea'):
                # Look for absolute addresses in operand
                target = self._parse_absolute_addr(op_str)
                if target and 0x200 <= target < self.rom.size and not (target & 1):
                    targets.add(target)
            elif mnemonic == 'move.l' and '#$' in op_str:
                # move.l #$XXXXXX, ...
                try:
                    imm_str = op_str.split('#$')[1].split(',')[0].strip()
                    val = int(imm_str, 16)
                    if 0x200 <= val < self.rom.size and not (val & 1):
                        targets.add(val)
                except (ValueError, IndexError):
                    pass
        return targets - self.visited

    def _scan_prologues(self):
        """Scan unvisited ROM for common function prologue patterns.

        Looks for LINK A5/A6 ($4E55/$4E56) and MOVEM.L regs,-(SP) ($48E7)
        at even addresses in the code area that haven't been visited yet.
        Borrowed from CPS1 recomp's approach.
        """
        targets = set()
        rom = self.rom
        code_start = 0x0E0000  # Pigskin code area
        i = code_start
        while i < rom.size - 4:
            if i not in self.visited and (i & 1) == 0:
                word = rom.read16(i)
                if word in (0x4E55, 0x4E56):
                    # LINK A5/A6 — classic function prologue
                    targets.add(i)
                    if i not in self.labels:
                        self.labels[i] = f"sub_{i:06X}"
                elif word == 0x48E7:
                    # MOVEM.L regs,-(SP) — register save prologue
                    targets.add(i)
                    if i not in self.labels:
                        self.labels[i] = f"sub_{i:06X}"
            i += 2
        return targets - self.visited

    def _parse_absolute_addr(self, op_str):
        """Extract absolute address from operand string."""
        # Match patterns like ($XXXX).l or ($XXXX).w or $XXXX
        for part in op_str.replace('(', '').replace(')', '').replace('.l', '').replace('.w', '').split(','):
            part = part.strip()
            if part.startswith('$'):
                try:
                    return int(part[1:], 16)
                except ValueError:
                    pass
            elif part.startswith('0x'):
                try:
                    return int(part, 16)
                except ValueError:
                    pass
        return None

    def _disassemble_block(self, start_addr):
        """Disassemble a basic block. Returns list of (target, is_call)."""
        targets = []
        addr = start_addr
        max_insns = 10000  # safety limit

        for _ in range(max_insns):
            if addr >= self.rom.size or addr in self.visited:
                break
            if addr & 1:
                break

            self.visited.add(addr)
            code = bytes(self.rom.data[addr:min(addr+10, self.rom.size)])
            insns = list(self.cs.disasm(code, addr, count=1))

            if not insns:
                break

            insn = insns[0]
            mnemonic = insn.mnemonic.lower()
            op_str = insn.op_str

            self.instructions[addr] = (mnemonic, op_str, insn.size, code[:insn.size])

            if mnemonic in self.CALL_MNEMONICS:
                target = self._extract_branch_target(insn, addr)
                if target is not None:
                    self.xrefs_to[target].add(addr)
                    self.call_graph[start_addr].add(target)
                    targets.append((target, True))
                    if target not in self.labels:
                        self.labels[target] = f"sub_{target:06X}"
                addr += insn.size
                continue

            elif mnemonic in ('bra', 'jmp'):
                target = self._extract_branch_target(insn, addr)
                if target is not None:
                    self.xrefs_to[target].add(addr)
                    targets.append((target, False))
                break

            elif mnemonic in ('rts', 'rte', 'rtr'):
                break

            elif mnemonic.startswith('b') and mnemonic not in self.BIT_MNEMONICS:
                target = self._extract_branch_target(insn, addr)
                if target is not None:
                    self.xrefs_to[target].add(addr)
                    targets.append((target, False))
                    if target not in self.labels:
                        self.labels[target] = f"loc_{target:06X}"
                addr += insn.size
                continue

            elif mnemonic.startswith('db'):
                target = self._extract_branch_target(insn, addr)
                if target is not None:
                    self.xrefs_to[target].add(addr)
                    targets.append((target, False))
                    if target not in self.labels:
                        self.labels[target] = f"loc_{target:06X}"
                addr += insn.size
                continue

            else:
                addr += insn.size

        return targets

    def _extract_branch_target(self, insn, addr):
        """Extract absolute target address from branch/call instruction."""
        op_str = insn.op_str.strip()

        # For DBcc: target is after the comma (e.g. "d1, $238")
        if ',' in op_str and insn.mnemonic.lower().startswith('db'):
            target_part = op_str.split(',', 1)[1].strip()
            if target_part.startswith('$'):
                try:
                    return int(target_part[1:], 16) & 0xFFFFFF
                except ValueError:
                    pass
            if target_part.startswith('0x'):
                try:
                    return int(target_part, 16) & 0xFFFFFF
                except ValueError:
                    pass

        if op_str.startswith('$'):
            try:
                return int(op_str[1:], 16) & 0xFFFFFF
            except ValueError:
                pass
        if op_str.startswith('0x'):
            try:
                return int(op_str, 16) & 0xFFFFFF
            except ValueError:
                pass

        # Absolute addressing modes: ($XXXX).l or ($XXXX).w
        if '(' in op_str and '$' in op_str:
            inner = op_str.replace('(', '').replace(')', '').replace('.l', '').replace('.w', '').strip()
            if inner.startswith('$'):
                try:
                    return int(inner[1:], 16) & 0xFFFFFF
                except ValueError:
                    pass

        if insn.operands:
            op = insn.operands[0]
            if hasattr(op, 'imm'):
                return op.imm & 0xFFFFFF
            if hasattr(op, 'mem') and hasattr(op.mem, 'disp'):
                if op.mem.base == 0:
                    return op.mem.disp & 0xFFFFFF

        return None

    def _build_functions(self, func_entries):
        """Build function objects from discovered entry points."""
        all_addrs = sorted(self.instructions.keys())
        if not all_addrs:
            return

        sorted_entries = sorted(func_entries & set(all_addrs))

        for i, entry in enumerate(sorted_entries):
            next_entry = sorted_entries[i + 1] if i + 1 < len(sorted_entries) else self.rom.size

            insn_addrs = []
            for addr in all_addrs:
                if addr < entry:
                    continue
                if addr >= next_entry:
                    break
                insn_addrs.append(addr)

            if not insn_addrs:
                continue

            end_addr = insn_addrs[-1]
            last_mnem = self.instructions[end_addr][0]
            last_size = self.instructions[end_addr][2]

            name = self.labels.get(entry, f"sub_{entry:06X}")

            # Collect all branch targets within this function (for local labels)
            local_labels = set()
            for ia in insn_addrs:
                for ref_from in self.xrefs_to.get(ia, set()):
                    if entry <= ref_from < next_entry:
                        local_labels.add(ia)

            self.functions[entry] = {
                'name': name,
                'start': entry,
                'end': end_addr + last_size,
                'size': (end_addr + last_size) - entry,
                'insn_count': len(insn_addrs),
                'insn_addrs': insn_addrs,
                'calls': sorted(self.call_graph.get(entry, set())),
                'has_return': last_mnem in ('rts', 'rte', 'rtr'),
                'local_labels': sorted(local_labels),
            }

    def get_disassembly(self, start=None, end=None):
        """Get formatted disassembly text."""
        lines = []
        addrs = sorted(self.instructions.keys())
        if start is not None:
            addrs = [a for a in addrs if a >= start]
        if end is not None:
            addrs = [a for a in addrs if a <= end]

        for addr in addrs:
            mnemonic, op_str, size, raw = self.instructions[addr]
            hex_bytes = ' '.join(f'{b:02X}' for b in raw)

            label = ""
            if addr in self.labels:
                label = f"\n{self.labels[addr]}:\n"

            xref = ""
            if addr in self.xrefs_to and len(self.xrefs_to[addr]) > 0:
                refs = ', '.join(f'${r:06X}' for r in sorted(self.xrefs_to[addr])[:5])
                xref = f"  ; xref: {refs}"

            lines.append(f"{label}  {addr:06X}:  {hex_bytes:<24s}  {mnemonic:<8s} {op_str}{xref}")

        return '\n'.join(lines)

    def export_json(self, path):
        """Export function map to JSON."""
        output = {
            'rom': {
                'title': self.rom.title_domestic,
                'serial': self.rom.serial,
                'size': self.rom.size,
                'entry_pc': self.rom.initial_pc,
                'initial_sp': self.rom.initial_sp,
                'checksum': self.rom.checksum,
            },
            'vectors': {name: f"0x{addr:06X}" for name, addr in self.rom.vectors.items()},
            'stats': {
                'total_instructions': len(self.instructions),
                'total_functions': len(self.functions),
                'total_xrefs': len(self.xrefs_to),
                'code_coverage_bytes': sum(self.instructions[a][2] for a in self.instructions),
            },
            'functions': {},
        }

        for addr in sorted(self.functions.keys()):
            func = self.functions[addr]
            output['functions'][f"0x{addr:06X}"] = {
                'name': func['name'],
                'start': f"0x{func['start']:06X}",
                'end': f"0x{func['end']:06X}",
                'size': func['size'],
                'insn_count': func['insn_count'],
                'calls': [f"0x{c:06X}" for c in func['calls']],
                'has_return': func['has_return'],
            }

        with open(path, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"\nExported {len(self.functions)} functions to {path}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Pigskin ROM Analyzer')
    parser.add_argument('rom', help='Path to Genesis ROM file')
    parser.add_argument('--output', '-o', default='functions.json', help='Output JSON path')
    parser.add_argument('--disasm', '-d', action='store_true', help='Print full disassembly')
    parser.add_argument('--disasm-func', type=str, help='Disassemble specific function (hex addr)')
    parser.add_argument('--stats', action='store_true', help='Print statistics')
    args = parser.parse_args()

    rom = GenesisROM(args.rom)
    rom.print_info()

    analyzer = M68KAnalyzer(rom)
    analyzer.analyze()

    if args.stats:
        print("\n=== Top 20 Largest Functions ===")
        funcs_by_size = sorted(analyzer.functions.values(), key=lambda f: f['insn_count'], reverse=True)
        for f in funcs_by_size[:20]:
            print(f"  {f['name']:<30s}  ${f['start']:06X}  {f['insn_count']:5d} insns  {f['size']:5d} bytes")

        print(f"\n=== Call Graph Stats ===")
        total_calls = sum(len(f['calls']) for f in analyzer.functions.values())
        print(f"  Total call edges: {total_calls}")
        leaf = sum(1 for f in analyzer.functions.values() if len(f['calls']) == 0)
        print(f"  Leaf functions (no calls): {leaf}")

        total_bytes = sum(analyzer.instructions[a][2] for a in analyzer.instructions)
        print(f"\n=== Coverage ===")
        print(f"  Code bytes discovered: {total_bytes} ({total_bytes/1024:.1f} KB)")
        print(f"  ROM utilization:       {total_bytes*100/rom.size:.1f}%")

    if args.disasm:
        print("\n=== Full Disassembly ===")
        print(analyzer.get_disassembly())

    if args.disasm_func:
        addr = int(args.disasm_func, 16)
        if addr in analyzer.functions:
            func = analyzer.functions[addr]
            print(f"\n=== {func['name']} (${func['start']:06X} - ${func['end']:06X}) ===")
            print(analyzer.get_disassembly(func['start'], func['end']))
        else:
            print(f"No function at ${addr:06X}")

    analyzer.export_json(args.output)


if __name__ == '__main__':
    main()
