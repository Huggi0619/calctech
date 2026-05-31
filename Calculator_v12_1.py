import tkinter as tk
from tkinter import ttk, messagebox
import math
import copy

MAX_ITER = 100

# IEC 60062 Farbcode-Tabelle: (Name, bg-Hex, fg-Hex, Ziffer, Multiplikator, Toleranz)
FARBEN = [
    ("Schwarz", "#000000", "#ffffff",  0,  1.0,           None     ),
    ("Braun",   "#795548", "#ffffff",  1,  10.0,          "±1%"    ),
    ("Rot",     "#f44336", "#ffffff",  2,  100.0,         "±2%"    ),
    ("Orange",  "#ff9800", "#000000",  3,  1000.0,        None     ),
    ("Gelb",    "#ffeb3b", "#000000",  4,  10000.0,       None     ),
    ("Grün",    "#4caf50", "#ffffff",  5,  100000.0,      "±0.5%"  ),
    ("Blau",    "#2196f3", "#ffffff",  6,  1000000.0,     "±0.25%" ),
    ("Violett", "#9c27b0", "#ffffff",  7,  10000000.0,    "±0.1%"  ),
    ("Grau",    "#9e9e9e", "#000000",  8,  100000000.0,   "±0.05%" ),
    ("Weiß",    "#ffffff", "#000000",  9,  1000000000.0,  None     ),
    ("Gold",    "#ffd700", "#000000",  None, 0.1,         "±5%"    ),
    ("Silber",  "#c0c0c0", "#000000",  None, 0.01,        "±10%"   ),
]

# ==========================================
# PARSE & OHM
# ==========================================

def parse_value(val_str):
    if val_str is None: return None
    val_str = str(val_str).replace(',', '.').strip()
    if not val_str: return None
    try:
        low = val_str.lower()
        if low.endswith('meg'):    return float(val_str[:-3]) * 1e6
        if val_str.endswith('T') or val_str.endswith('t'):  return float(val_str[:-1]) * 1e12
        if val_str.endswith('G') or val_str.endswith('g'):  return float(val_str[:-1]) * 1e9
        if low.endswith('k'):      return float(val_str[:-1]) * 1e3
        if val_str.endswith('M'):  return float(val_str[:-1]) * 1e6
        if val_str.endswith('m'):  return float(val_str[:-1]) * 1e-3
        if val_str.endswith('μ') or low.endswith('u'):
            return float(val_str[:-1]) * 1e-6
        if low.endswith('n'):      return float(val_str[:-1]) * 1e-9
        if low.endswith('p'):      return float(val_str[:-1]) * 1e-12
        return float(val_str)
    except ValueError: return None


def _read_val(entry):
    if entry is None: return None
    raw = entry.get().strip()
    if not raw: return None
    return parse_value(raw)


def _format_with_unit(val, sf):
    if val is None: return "", ""
    a = abs(val)
    if a == 0: return "0", ""
    prefixes = [
        (1e12, "T"), (1e9, "G"), (1e6, "M"), (1e3, "k"),
        (1.0, ""), (1e-3, "m"), (1e-6, "μ"), (1e-9, "n"), (1e-12, "p")
    ]
    for limit, unit in prefixes:
        if a >= limit * 0.999:
            scaled = val / limit
            s = f"{scaled:.{sf}g}"
            if 'e' in s:
                s = f"{scaled:.{sf}f}".rstrip('0').rstrip('.')
            return s, unit
    return f"{val:.{sf}g}", ""


def apply_ohm(comp):
    if comp['R'] is not None and comp['I'] is not None and comp['U'] is None:
        comp['U'] = comp['R'] * comp['I']
    if comp['U'] is not None and comp['R'] is not None and comp['I'] is None and comp['R'] != 0:
        comp['I'] = comp['U'] / comp['R']
    if comp['U'] is not None and comp['I'] is not None and comp['R'] is None and comp['I'] != 0:
        comp['R'] = comp['U'] / comp['I']
    if comp['U'] is not None and comp['I'] is not None and comp['P'] is None:
        comp['P'] = comp['U'] * comp['I']
    if comp['U'] is not None and comp['R'] is not None and comp['P'] is None and comp['R'] != 0:
        comp['P'] = comp['U']**2 / comp['R']
    if comp['I'] is not None and comp['R'] is not None and comp['P'] is None:
        comp['P'] = comp['I']**2 * comp['R']
    if comp['P'] is not None and comp['U'] is not None and comp['I'] is None and comp['U'] != 0:
        comp['I'] = comp['P'] / comp['U']
    if comp['P'] is not None and comp['I'] is not None and comp['U'] is None and comp['I'] != 0:
        comp['U'] = comp['P'] / comp['I']
    if comp['P'] is not None and comp['I'] is not None and comp['R'] is None and comp['I'] != 0:
        comp['R'] = comp['P'] / comp['I']**2
    if comp['U'] is not None and comp['P'] is not None and comp['R'] is None and comp['P'] != 0:
        comp['R'] = comp['U']**2 / comp['P']
    if comp['P'] is not None and comp['R'] is not None and comp['P'] >= 0 and comp['R'] > 0:
        if comp['I'] is None: comp['I'] = math.sqrt(comp['P'] / comp['R'])
        if comp['U'] is None: comp['U'] = math.sqrt(comp['P'] * comp['R'])


def apply_sum_logic(total_dict, key, part_dicts):
    total_val = total_dict[key]
    parts_vals = [p[key] for p in part_dicts]
    if total_val is None and all(x is not None for x in parts_vals) and len(parts_vals) > 0:
        total_dict[key] = sum(parts_vals); return True
    if total_val is not None and parts_vals.count(None) == 1:
        m_idx = parts_vals.index(None)
        part_dicts[m_idx][key] = max(0.0, total_val - sum(x for x in parts_vals if x is not None))
        return True
    return False


def apply_parallel_r_logic(total_dict, part_dicts):
    total_r = total_dict['R']
    parts_r  = [p['R'] for p in part_dicts]
    if total_r is None and all(x is not None and x > 0 for x in parts_r) and len(parts_r) > 0:
        total_dict['R'] = 1.0 / sum(1.0/x for x in parts_r); return True
    if total_r is not None and total_r > 0 and parts_r.count(None) == 1:
        m_idx = parts_r.index(None)
        known_inv = sum(1.0/x for x in parts_r if x is not None and x > 0)
        inv_total = 1.0 / total_r
        diff = inv_total - known_inv
        if diff > abs(inv_total) * 1e-9 + 1e-15:
            part_dicts[m_idx]['R'] = 1.0 / diff; return True
    return False


def distribute_values(v_total, v1, v2, is_parallel):
    if is_parallel:
        u_val = next((x for x in [v_total['U'], v1['U'], v2['U']] if x is not None), None)
        if u_val is not None: v_total['U'] = v1['U'] = v2['U'] = u_val
        apply_sum_logic(v_total, 'I', [v1, v2])
        apply_parallel_r_logic(v_total, [v1, v2])
    else:
        i_val = next((x for x in [v_total['I'], v1['I'], v2['I']] if x is not None), None)
        if i_val is not None: v_total['I'] = v1['I'] = v2['I'] = i_val
        apply_sum_logic(v_total, 'U', [v1, v2])
        parts_r = [v1['R'], v2['R']]
        if v_total['R'] is None and all(x is not None for x in parts_r):
            v_total['R'] = sum(parts_r)
        elif v_total['R'] is not None and parts_r.count(None) == 1:
            if v1['R'] is None: v1['R'] = max(0.0, v_total['R'] - v2['R'])
            else:               v2['R'] = max(0.0, v_total['R'] - v1['R'])
    apply_sum_logic(v_total, 'P', [v1, v2])


def sync_group_with_parts(c, group_total, indices, is_parallel):
    group_parts = [c[idx] for idx in indices]
    if is_parallel:
        u_val = next((p['U'] for p in [group_total] + group_parts if p['U'] is not None), None)
        if u_val is not None:
            group_total['U'] = u_val
            for p in group_parts: p['U'] = u_val
        apply_sum_logic(group_total, 'I', group_parts)
        apply_parallel_r_logic(group_total, group_parts)
    else:
        i_val = next((p['I'] for p in [group_total] + group_parts if p['I'] is not None), None)
        if i_val is not None:
            group_total['I'] = i_val
            for p in group_parts: p['I'] = i_val
        apply_sum_logic(group_total, 'U', group_parts)
        total_r = group_total['R']
        parts_r  = [p['R'] for p in group_parts]
        if total_r is None and all(x is not None for x in parts_r) and len(parts_r) > 0:
            group_total['R'] = sum(parts_r)
        elif total_r is not None and parts_r.count(None) == 1:
            m_idx = parts_r.index(None)
            group_parts[m_idx]['R'] = max(0.0, total_r - sum(x for x in parts_r if x is not None))
    apply_sum_logic(group_total, 'P', group_parts)


def solve_sudoku_universal(c, groups_def):
    for _ in range(MAX_ITER):
        prev = copy.deepcopy(c)
        for comp in c: apply_ohm(comp)
        v_groups = [apply_group_logic_initial(c, g['indices'], g['parallel']) for g in groups_def]
        if not v_groups: break
        v_stages = [copy.deepcopy(v_groups[0])]
        for i in range(1, len(groups_def)):
            v_new = {'U': None, 'I': None, 'R': None, 'P': None}
            distribute_values(v_new, v_stages[i-1], v_groups[i], groups_def[i]['global_parallel'])
            v_stages.append(v_new)
        for k in ['U', 'I', 'R', 'P']:
            if c[0][k] is not None:       v_stages[-1][k] = c[0][k]
            elif v_stages[-1][k] is not None: c[0][k] = v_stages[-1][k]
        for i in range(len(groups_def) - 1, 0, -1):
            distribute_values(v_stages[i], v_stages[i-1], v_groups[i], groups_def[i]['global_parallel'])
        v_groups[0] = copy.deepcopy(v_stages[0])
        for i, g in enumerate(groups_def):
            sync_group_with_parts(c, v_groups[i], g['indices'], g['parallel'])
        if prev == c: break


def apply_group_logic_initial(c, indices, is_parallel):
    v = {'U': None, 'I': None, 'R': None, 'P': None}
    parts = [c[idx] for idx in indices]
    if is_parallel:
        u_vals = [p['U'] for p in parts if p['U'] is not None]
        if u_vals: v['U'] = u_vals[0]
        i_parts = [p['I'] for p in parts]
        if all(x is not None for x in i_parts): v['I'] = sum(i_parts)
        r_parts = [p['R'] for p in parts]
        if all(x is not None and x > 0 for x in r_parts):
            v['R'] = 1.0 / sum(1.0/x for x in r_parts)
    else:
        i_vals = [p['I'] for p in parts if p['I'] is not None]
        if i_vals: v['I'] = i_vals[0]
        u_parts = [p['U'] for p in parts]
        if all(x is not None for x in u_parts): v['U'] = sum(u_parts)
        r_parts = [p['R'] for p in parts]
        if all(x is not None for x in r_parts): v['R'] = sum(r_parts)
    p_parts = [p['P'] for p in parts]
    if all(x is not None for x in p_parts): v['P'] = sum(p_parts)
    return v


def validate_inputs(vals_list, names):
    warnings = []
    for name, vals in zip(names, vals_list):
        r, i, u, p = vals.get('R'), vals.get('I'), vals.get('U'), vals.get('P')
        if r is not None and r <= 0:
            warnings.append(f"{name}: R = {r} Ω ungültig (muss > 0 sein)")
        if i is not None and i < 0:
            warnings.append(f"{name}: I = {i} A negativ")
        if u is not None and u < 0:
            warnings.append(f"{name}: U = {u} V negativ")
        if p is not None and p < 0:
            warnings.append(f"{name}: P = {p} W negativ")
    return warnings


def check_consistency(vals, name, tol=1e-3):
    u, i, r, p = vals.get('U'), vals.get('I'), vals.get('R'), vals.get('P')
    issues = []
    if u is not None and i is not None and r is not None and r != 0:
        expected_u = r * i
        if abs(expected_u - u) / max(abs(u), 1e-12) > tol:
            issues.append(f"{name}: U={u:.4g}V ≠ R·I={expected_u:.4g}V")
    if u is not None and i is not None and p is not None:
        expected_p = u * i
        if abs(expected_p - p) / max(abs(p), 1e-12) > tol:
            issues.append(f"{name}: P={p:.4g}W ≠ U·I={expected_p:.4g}W")
    return issues


def _run_consistency_check(vals_list, names):
    """Führt validate_inputs + check_consistency durch und zeigt Warnung bei Problemen."""
    problems = validate_inputs(vals_list, names)
    for name, vals in zip(names, vals_list):
        problems.extend(check_consistency(vals, name))
    if problems:
        messagebox.showwarning(
            "Konsistenzprüfung — Widerspruch erkannt",
            "\n".join(problems)
        )


# ==========================================
# ENERGIEKOSTEN — BIDIREKTIONALER SOLVER
# ==========================================
#
# Gleichungen:
#   cost_tag   = P * h_tag   * tage * pr_tag   / K     (K = 100000)
#   cost_nacht = P * h_nacht * tage * pr_nacht / K
#   cost_total = cost_tag + cost_nacht
#   kwh_gesamt = P * (h_tag + h_nacht) * tage / 1000
#
# Jede Gleichung wird nach jeder Unbekannten aufgelöst;
# iteriert bis zum Fixpunkt (max. 50 Runden).

def solve_costs_bidirectional(v):
    K = 100_000.0  # = 1000 Wh/kWh × 100 Rp/CHF

    def _nz(*keys):
        return all(v[k] is not None and v[k] != 0 for k in keys)

    def _kn(*keys):
        return all(v[k] is not None for k in keys)

    for _ in range(50):
        prev = dict(v)

        # --- cost_tag = P * h_tag * tage * pr_tag / K ---
        if v['cost_tag'] is None and _kn('P', 'h_tag', 'tage', 'pr_tag'):
            v['cost_tag'] = v['P'] * v['h_tag'] * v['tage'] * v['pr_tag'] / K
        if v['cost_tag'] is not None:
            ct = v['cost_tag']
            if v['P']      is None and _nz('h_tag',   'tage', 'pr_tag'):
                v['P']      = ct * K / (v['h_tag']   * v['tage'] * v['pr_tag'])
            if v['h_tag']  is None and _nz('P',       'tage', 'pr_tag'):
                v['h_tag']  = ct * K / (v['P']       * v['tage'] * v['pr_tag'])
            if v['tage']   is None and _nz('P', 'h_tag',       'pr_tag'):
                v['tage']   = ct * K / (v['P']       * v['h_tag'] * v['pr_tag'])
            if v['pr_tag'] is None and _nz('P', 'h_tag', 'tage'        ):
                v['pr_tag'] = ct * K / (v['P']       * v['h_tag'] * v['tage'])

        # --- cost_nacht = P * h_nacht * tage * pr_nacht / K ---
        if v['cost_nacht'] is None and _kn('P', 'h_nacht', 'tage', 'pr_nacht'):
            v['cost_nacht'] = v['P'] * v['h_nacht'] * v['tage'] * v['pr_nacht'] / K
        if v['cost_nacht'] is not None:
            cn = v['cost_nacht']
            if v['P']        is None and _nz('h_nacht', 'tage', 'pr_nacht'):
                v['P']        = cn * K / (v['h_nacht'] * v['tage'] * v['pr_nacht'])
            if v['h_nacht']  is None and _nz('P',       'tage', 'pr_nacht'):
                v['h_nacht']  = cn * K / (v['P']       * v['tage'] * v['pr_nacht'])
            if v['tage']     is None and _nz('P', 'h_nacht',     'pr_nacht'):
                v['tage']     = cn * K / (v['P']       * v['h_nacht'] * v['pr_nacht'])
            if v['pr_nacht'] is None and _nz('P', 'h_nacht', 'tage'        ):
                v['pr_nacht'] = cn * K / (v['P']       * v['h_nacht'] * v['tage'])

        # --- cost_total = cost_tag + cost_nacht ---
        if v['cost_total'] is None and _kn('cost_tag', 'cost_nacht'):
            v['cost_total'] = v['cost_tag'] + v['cost_nacht']
        if v['cost_tag']   is None and _kn('cost_total', 'cost_nacht'):
            v['cost_tag']   = max(0.0, v['cost_total'] - v['cost_nacht'])
        if v['cost_nacht'] is None and _kn('cost_total', 'cost_tag'):
            v['cost_nacht'] = max(0.0, v['cost_total'] - v['cost_tag'])

        # --- kwh_gesamt = P * (h_tag + h_nacht) * tage / 1000 ---
        if _kn('h_tag', 'h_nacht'):
            h_sum = v['h_tag'] + v['h_nacht']
            if v['kwh_gesamt'] is None and _kn('P', 'tage'):
                v['kwh_gesamt'] = v['P'] * h_sum * v['tage'] / 1000
            if v['P']    is None and v['kwh_gesamt'] is not None and h_sum > 0 and _nz('tage'):
                v['P']    = v['kwh_gesamt'] * 1000 / (h_sum * v['tage'])
            if v['tage'] is None and v['kwh_gesamt'] is not None and h_sum > 0 and _nz('P'):
                v['tage'] = v['kwh_gesamt'] * 1000 / (v['P'] * h_sum)

        # Aus kwh + einem der Stunden-Werte den anderen ableiten
        if v['kwh_gesamt'] is not None and _nz('P', 'tage'):
            h_sum = v['kwh_gesamt'] * 1000 / (v['P'] * v['tage'])
            if v['h_tag']   is not None and v['h_nacht'] is None:
                v['h_nacht'] = max(0.0, h_sum - v['h_tag'])
            if v['h_nacht'] is not None and v['h_tag']   is None:
                v['h_tag']   = max(0.0, h_sum - v['h_nacht'])

        if v == prev:
            break


# ==========================================
# SZENARIEN-SOLVER
# ==========================================

def solve_szenarien(c1, c2, groups_def, coupled_r_indices, ug_linked):
    """Löst zwei Szenarien gleichzeitig. Koppelt R-Werte und optional Ug
    zwischen den Szenarien und iteriert bis zum gemeinsamen Fixpunkt."""
    def _sync():
        for idx in coupled_r_indices:
            if idx < len(c1) and idx < len(c2):
                if c1[idx]['R'] is not None and c2[idx]['R'] is None:
                    c2[idx]['R'] = c1[idx]['R']
                elif c2[idx]['R'] is not None and c1[idx]['R'] is None:
                    c1[idx]['R'] = c2[idx]['R']
        if ug_linked and c1 and c2:
            if c1[0]['U'] is not None and c2[0]['U'] is None:
                c2[0]['U'] = c1[0]['U']
            elif c2[0]['U'] is not None and c1[0]['U'] is None:
                c1[0]['U'] = c2[0]['U']

    for _ in range(MAX_ITER):
        prev1 = copy.deepcopy(c1)
        prev2 = copy.deepcopy(c2)
        _sync()
        solve_sudoku_universal(c1, groups_def)
        solve_sudoku_universal(c2, groups_def)
        _sync()
        if c1 == prev1 and c2 == prev2:
            break


# ==========================================
# BATTERIE / INNENWIDERSTAND — SOLVER
# ==========================================
#
# Gleichungen:
#   Uk  = E - Ri*I          Klemmspannung
#   I   = E / (Ri + Ra)     Stromfluss
#   Uk  = Ra * I            Ohm an Last
#   Pa  = Uk * I = Ra*I²    Nutzleistung
#   Pi  = Ri * I²           Verlustleistung
#   P_ges = Pa + Pi = E*I   Gesamtleistung
#   Isc = E / Ri            Kurzschlussstrom

def solve_batterie(v):
    def _kn(*keys): return all(v[k] is not None for k in keys)
    def _nz(*keys): return all(v[k] is not None and v[k] != 0 for k in keys)

    for _ in range(50):
        prev = dict(v)

        # Uk = E - Ri*I
        if v['Uk']  is None and _kn('E', 'Ri', 'I'):
            v['Uk'] = v['E'] - v['Ri'] * v['I']
        if v['E']   is None and _kn('Uk', 'Ri', 'I'):
            v['E']  = v['Uk'] + v['Ri'] * v['I']
        if v['Ri']  is None and _kn('E', 'Uk', 'I') and _nz('I'):
            v['Ri'] = (v['E'] - v['Uk']) / v['I']
        if v['I']   is None and _kn('E', 'Uk', 'Ri') and _nz('Ri'):
            v['I']  = (v['E'] - v['Uk']) / v['Ri']

        # I = E / (Ri + Ra)
        if v['I']   is None and _kn('E', 'Ri', 'Ra'):
            d = v['Ri'] + v['Ra']
            if d != 0: v['I'] = v['E'] / d
        if v['E']   is None and _kn('I', 'Ri', 'Ra'):
            v['E']  = v['I'] * (v['Ri'] + v['Ra'])
        if v['Ra']  is None and _kn('E', 'I', 'Ri') and _nz('I'):
            v['Ra'] = v['E'] / v['I'] - v['Ri']
        if v['Ri']  is None and _kn('E', 'I', 'Ra') and _nz('I'):
            v['Ri'] = v['E'] / v['I'] - v['Ra']

        # Uk = Ra * I
        if v['Uk']  is None and _kn('Ra', 'I'):
            v['Uk'] = v['Ra'] * v['I']
        if v['Ra']  is None and _kn('Uk', 'I') and _nz('I'):
            v['Ra'] = v['Uk'] / v['I']
        if v['I']   is None and _kn('Uk', 'Ra') and _nz('Ra'):
            v['I']  = v['Uk'] / v['Ra']

        # Pa = Uk * I
        if v['Pa']  is None and _kn('Uk', 'I'):
            v['Pa'] = v['Uk'] * v['I']
        if v['Uk']  is None and _kn('Pa', 'I') and _nz('I'):
            v['Uk'] = v['Pa'] / v['I']
        if v['I']   is None and _kn('Pa', 'Uk') and _nz('Uk'):
            v['I']  = v['Pa'] / v['Uk']

        # Pa = Ra * I²
        if v['Pa']  is None and _kn('Ra', 'I'):
            v['Pa'] = v['Ra'] * v['I']**2
        if v['Ra']  is None and _kn('Pa', 'I') and _nz('I'):
            v['Ra'] = v['Pa'] / v['I']**2
        if v['I']   is None and _kn('Pa', 'Ra') and _nz('Ra') and v['Pa'] >= 0:
            v['I']  = math.sqrt(v['Pa'] / v['Ra'])

        # Pi = Ri * I²
        if v['Pi']  is None and _kn('Ri', 'I'):
            v['Pi'] = v['Ri'] * v['I']**2
        if v['Ri']  is None and _kn('Pi', 'I') and _nz('I'):
            v['Ri'] = v['Pi'] / v['I']**2
        if v['I']   is None and _kn('Pi', 'Ri') and _nz('Ri') and v['Pi'] >= 0:
            v['I']  = math.sqrt(v['Pi'] / v['Ri'])

        # P_ges = E * I
        if v['P_ges'] is None and _kn('E', 'I'):
            v['P_ges'] = v['E'] * v['I']
        if v['E']     is None and _kn('P_ges', 'I') and _nz('I'):
            v['E']     = v['P_ges'] / v['I']
        if v['I']     is None and _kn('P_ges', 'E') and _nz('E'):
            v['I']     = v['P_ges'] / v['E']

        # P_ges = Pa + Pi
        if v['P_ges'] is None and _kn('Pa', 'Pi'):
            v['P_ges'] = v['Pa'] + v['Pi']
        if v['Pa']    is None and _kn('P_ges', 'Pi'):
            v['Pa']    = max(0.0, v['P_ges'] - v['Pi'])
        if v['Pi']    is None and _kn('P_ges', 'Pa'):
            v['Pi']    = max(0.0, v['P_ges'] - v['Pa'])

        # Isc = E / Ri
        if v['Isc'] is None and _kn('E', 'Ri') and _nz('Ri'):
            v['Isc'] = v['E'] / v['Ri']
        if v['E']   is None and _kn('Isc', 'Ri'):
            v['E']   = v['Isc'] * v['Ri']
        if v['Ri']  is None and _kn('Isc', 'E') and _nz('Isc'):
            v['Ri']  = v['E'] / v['Isc']

        if v == prev:
            break


# ==========================================
# SZENARIEN-VISUAL HELPER SOLVERS
# ==========================================

def _sz_dual_loop(root1, root2, leaves1, leaves2, coupled_idx_set, ug_linked):
    """Outer fixed-point loop: sync coupled values, solve each tree, repeat."""
    def _sync():
        for i in coupled_idx_set:
            r1, r2 = leaves1[i].vals['R'], leaves2[i].vals['R']
            if r1 is not None and r2 is None: leaves2[i].vals['R'] = r1
            elif r2 is not None and r1 is None: leaves1[i].vals['R'] = r2
        if ug_linked:
            u1, u2 = root1.vals['U'], root2.vals['U']
            if u1 is not None and u2 is None: root2.vals['U'] = u1
            elif u2 is not None and u1 is None: root1.vals['U'] = u2

    for _ in range(MAX_ITER):
        s1, s2 = _bk_snapshot(root1), _bk_snapshot(root2)
        _sync()
        solve_baukasten(root1)
        solve_baukasten(root2)
        _sync()
        if _bk_snapshot(root1) == s1 and _bk_snapshot(root2) == s2:
            break


def _sz_bisect(root1, root2, leaves1, leaves2, coupled_idx_set, ug_linked):
    """
    Falls nach FPI genau 1 gekoppeltes R unbekannt ist und Ug verknüpft:
    Bisektion findet R_x sodass beide Szenarien dasselbe Ug liefern.
    """
    unknown = [i for i in coupled_idx_set
               if leaves1[i].vals['R'] is None and leaves2[i].vals['R'] is None]
    if len(unknown) != 1 or not ug_linked:
        return

    idx = unknown[0]

    def _residual(R_x):
        t1 = copy.deepcopy(root1)
        t2 = copy.deepcopy(root2)
        t1.all_r_nodes()[idx].vals['R'] = R_x
        t2.all_r_nodes()[idx].vals['R'] = R_x
        solve_baukasten(t1); solve_baukasten(t2)
        u1, u2 = t1.vals['U'], t2.vals['U']
        return (u1 - u2) if (u1 is not None and u2 is not None) else None

    lo, hi = 1e-6, 1e9
    r_lo, r_hi = _residual(lo), _residual(hi)
    if r_lo is None or r_hi is None or r_lo * r_hi > 0:
        return

    for _ in range(60):
        mid   = (lo + hi) * 0.5
        r_mid = _residual(mid)
        if r_mid is None: return
        if abs(r_mid) < 1e-9: break
        if r_lo * r_mid <= 0: hi, r_hi = mid, r_mid
        else:                  lo, r_lo = mid, r_mid

    R_solved = (lo + hi) * 0.5
    leaves1[idx].vals['R'] = R_solved
    leaves2[idx].vals['R'] = R_solved
    _sz_dual_loop(root1, root2, leaves1, leaves2, coupled_idx_set, ug_linked)


# ==========================================
# TOOLTIP
# ==========================================

class _Tooltip:
    """Leichtgewichtiger Tooltip — erscheint nach 1 s Hover-Verzögerung."""
    def __init__(self, widget, text, delay=1000):
        self._tip    = None
        self._after  = None
        self._widget = widget
        self._text   = text
        self._delay  = delay
        widget.bind("<Enter>",       self._on_enter,  add="+")
        widget.bind("<Leave>",       self._on_leave,  add="+")
        widget.bind("<ButtonPress>", self._on_leave,  add="+")

    def _on_enter(self, event):
        self._cancel()
        self._after = self._widget.after(self._delay, self._show)

    def _on_leave(self, event=None):
        self._cancel()
        self._hide()

    def _cancel(self):
        if self._after is not None:
            try:
                self._widget.after_cancel(self._after)
            except tk.TclError:
                pass
            self._after = None

    def _show(self):
        self._after = None
        widget = self._widget
        x = widget.winfo_rootx() + 24
        y = widget.winfo_rooty() + widget.winfo_height() + 6
        self._tip = tw = tk.Toplevel(widget)
        tw.overrideredirect(True)
        tw.attributes("-topmost", True)
        tk.Label(tw, text=self._text, bg="#1e293b", fg="#f1f5f9",
                 font=("Segoe UI", 9), padx=10, pady=5,
                 relief=tk.FLAT, justify=tk.LEFT).pack()
        tw.update_idletasks()
        if x + tw.winfo_width() > widget.winfo_screenwidth():
            x = widget.winfo_screenwidth() - tw.winfo_width() - 8
        tw.geometry(f"+{x}+{y}")

    def _hide(self):
        if self._tip:
            try:
                self._tip.destroy()
            except tk.TclError:
                pass
            self._tip = None


# ==========================================
# CIRCUIT NODE
# ==========================================

class CircuitNode:
    def __init__(self, ntype, label='', r_val=None):
        self.type     = ntype
        self.label    = label
        self.r_val    = r_val
        self.children = []
        self.vals     = {'U': None, 'I': None, 'R': None, 'P': None}

    def formula(self):
        if self.type == 'R': return self.label
        op = ' + ' if self.type == 'series' else ' || '
        inner = op.join(c.formula() for c in self.children)
        return f'({inner})' if len(self.children) > 1 else inner

    def all_r_nodes(self):
        if self.type == 'R': return [self]
        result = []
        for c in self.children: result.extend(c.all_r_nodes())
        return result


# ==========================================
# REKURSIVER SOLVER (BAUKASTEN)
# ==========================================

def _bk_ohm(v):
    apply_ohm(v)

def _bk_ohm_all(node):
    _bk_ohm(node.vals)
    for c in node.children: _bk_ohm_all(c)

def _bk_up(node):
    if node.type == 'R': return
    for c in node.children: _bk_up(c)
    v  = node.vals
    cv = [c.vals for c in node.children]
    if node.type == 'series':
        r_list = [x['R'] for x in cv]
        if v['R'] is None and all(r is not None for r in r_list):
            v['R'] = sum(r_list)
        elif v['R'] is not None and r_list.count(None) == 1:
            idx = r_list.index(None)
            cv[idx]['R'] = max(0.0, v['R'] - sum(r for r in r_list if r is not None))
        u_list = [x['U'] for x in cv]
        if v['U'] is None and all(u is not None for u in u_list):
            v['U'] = sum(u_list)
        elif v['U'] is not None and u_list.count(None) == 1:
            idx = u_list.index(None)
            cv[idx]['U'] = max(0.0, v['U'] - sum(u for u in u_list if u is not None))
        i_vals = [x['I'] for x in cv if x['I'] is not None]
        if v['I'] is None and i_vals: v['I'] = i_vals[0]
        p_list = [x['P'] for x in cv]
        if v['P'] is None and all(p is not None for p in p_list):
            v['P'] = sum(p_list)
        elif v['P'] is not None and p_list.count(None) == 1:
            idx = p_list.index(None)
            cv[idx]['P'] = max(0.0, v['P'] - sum(p for p in p_list if p is not None))
    else:
        r_list = [x['R'] for x in cv]
        if v['R'] is None and all(r is not None and r > 0 for r in r_list):
            v['R'] = 1.0 / sum(1.0/r for r in r_list)
        elif v['R'] is not None and v['R'] > 0 and r_list.count(None) == 1:
            m_idx = r_list.index(None)
            known_inv = sum(1.0/r for r in r_list if r is not None and r > 0)
            inv_total = 1.0 / v['R']
            diff = inv_total - known_inv
            if diff > abs(inv_total) * 1e-9 + 1e-15:
                cv[m_idx]['R'] = 1.0 / diff
        u_vals = [x['U'] for x in cv if x['U'] is not None]
        if v['U'] is None and u_vals: v['U'] = u_vals[0]
        i_list = [x['I'] for x in cv]
        if v['I'] is None and all(i is not None for i in i_list):
            v['I'] = sum(i_list)
        elif v['I'] is not None and i_list.count(None) == 1:
            idx = i_list.index(None)
            cv[idx]['I'] = max(0.0, v['I'] - sum(i for i in i_list if i is not None))
        p_list = [x['P'] for x in cv]
        if v['P'] is None and all(p is not None for p in p_list):
            v['P'] = sum(p_list)
        elif v['P'] is not None and p_list.count(None) == 1:
            idx = p_list.index(None)
            cv[idx]['P'] = max(0.0, v['P'] - sum(p for p in p_list if p is not None))

def _bk_down(node):
    if node.type == 'R': return
    v  = node.vals
    cv = [c.vals for c in node.children]
    if node.type == 'series':
        if v['I'] is not None:
            for c in node.children:
                if c.vals['I'] is None: c.vals['I'] = v['I']
        u_list = [x['U'] for x in cv]
        if v['U'] is not None and u_list.count(None) == 1:
            idx = u_list.index(None)
            cv[idx]['U'] = max(0.0, v['U'] - sum(u for u in u_list if u is not None))
        r_list = [x['R'] for x in cv]
        if v['R'] is not None and r_list.count(None) == 1:
            idx = r_list.index(None)
            cv[idx]['R'] = max(0.0, v['R'] - sum(r for r in r_list if r is not None))
        p_list = [x['P'] for x in cv]
        if v['P'] is not None and p_list.count(None) == 1:
            idx = p_list.index(None)
            cv[idx]['P'] = max(0.0, v['P'] - sum(p for p in p_list if p is not None))
    else:
        if v['U'] is not None:
            for c in node.children:
                if c.vals['U'] is None: c.vals['U'] = v['U']
        i_list = [x['I'] for x in cv]
        if v['I'] is not None and i_list.count(None) == 1:
            idx = i_list.index(None)
            cv[idx]['I'] = max(0.0, v['I'] - sum(i for i in i_list if i is not None))
        r_list = [x['R'] for x in cv]
        if v['R'] is not None and v['R'] > 0 and r_list.count(None) == 1:
            m_idx = r_list.index(None)
            known_inv = sum(1.0/r for r in r_list if r is not None and r > 0)
            inv_total = 1.0 / v['R']
            diff = inv_total - known_inv
            if diff > abs(inv_total) * 1e-9 + 1e-15:
                cv[m_idx]['R'] = 1.0 / diff
        p_list = [x['P'] for x in cv]
        if v['P'] is None and all(p is not None for p in p_list):
            v['P'] = sum(p_list)
        elif v['P'] is not None and p_list.count(None) == 1:
            idx = p_list.index(None)
            cv[idx]['P'] = max(0.0, v['P'] - sum(p for p in p_list if p is not None))
    for c in node.children: _bk_down(c)

def _bk_snapshot(node):
    s = {id(node): dict(node.vals)}
    for c in node.children: s.update(_bk_snapshot(c))
    return s

def solve_baukasten(root):
    for _ in range(MAX_ITER):
        prev = _bk_snapshot(root)
        _bk_ohm_all(root)
        _bk_up(root)
        _bk_ohm_all(root)
        _bk_down(root)
        _bk_ohm_all(root)
        if _bk_snapshot(root) == prev: break


# ==========================================
# ZEICHNUNG
# ==========================================

_RW, _RH = 82, 48
_PAD = 14
_WIRE = 20
_RAIL = 14
_BG = ["#f0fdf4", "#eff6ff", "#fff7ed", "#fdf2f8", "#fdf4ff"]

def _measure(node):
    if node.type == 'R': return _RW, _RH
    child_sizes = [_measure(c) for c in node.children]
    if node.type == 'series':
        w = sum(cw for cw, _ in child_sizes) + _WIRE * (len(child_sizes) - 1) + 2 * _PAD
        h = max(ch for _, ch in child_sizes) + 2 * _PAD
    else:
        w = max(cw for cw, _ in child_sizes) + 2 * _RAIL + 2 * _PAD
        h = sum(ch for _, ch in child_sizes) + _WIRE * (len(child_sizes) - 1) + 2 * _PAD
    return w, h

def _draw_node(canvas, node, left, mid_y, selected_set, hit_map, depth, top_node,
               leaf_map=None):
    w, h = _measure(node)
    top = mid_y - h // 2
    if node.type == 'R':
        sel  = top_node in selected_set
        fill = "#bfdbfe" if sel else "#f0f9ff"
        oc   = "#1d4ed8" if sel else "#64748b"
        ow   = 3 if sel else 1
        rid  = canvas.create_rectangle(left, top, left + w, top + h,
                                        fill=fill, outline=oc, width=ow)
        canvas.create_text(left + w // 2, mid_y - 9,
                           text=node.label, font=("Segoe UI", 10, "bold"), fill="#1e293b")
        rv = f"{node.r_val:g} Ω" if node.r_val is not None else "? Ω"
        canvas.create_text(left + w // 2, mid_y + 9,
                           text=rv, font=("Segoe UI", 9), fill="#475569")
        hit_map[rid] = top_node
        if leaf_map is not None:
            leaf_map[rid] = node          # Blattknoten-Zuordnung für Popup
        return
    sel = top_node in selected_set
    bg  = _BG[depth % len(_BG)]
    oc  = "#1d4ed8" if sel else "#cbd5e1"
    ow  = 2 if sel else 1
    canvas.create_rectangle(left, top, left + w, top + h,
                            fill=bg, outline=oc, width=ow,
                            dash=() if sel else (5, 3))
    if node.type == 'series':
        cx = left + _PAD
        for i, child in enumerate(node.children):
            cw, _ = _measure(child)
            if i > 0:
                canvas.create_line(cx, mid_y, cx + _WIRE, mid_y, fill="#475569", width=2)
                cx += _WIRE
            _draw_node(canvas, child, cx, mid_y, selected_set, hit_map, depth + 1, top_node,
                       leaf_map)
            cx += cw
    else:
        inner_w  = max(_measure(c)[0] for c in node.children)
        rail_l   = left + _PAD
        rail_r   = left + w - _PAD
        child_mids, cur_y = [], top + _PAD
        for child in node.children:
            _, ch = _measure(child)
            child_mids.append(cur_y + ch // 2)
            cur_y += ch + _WIRE
        canvas.create_line(rail_l, child_mids[0], rail_l, child_mids[-1], fill="#475569", width=2)
        canvas.create_line(rail_r, child_mids[0], rail_r, child_mids[-1], fill="#475569", width=2)
        for i, child in enumerate(node.children):
            cw, _ = _measure(child)
            cl = left + _PAD + _RAIL + (inner_w - cw) // 2
            _draw_node(canvas, child, cl, child_mids[i], selected_set, hit_map, depth + 1,
                       top_node, leaf_map)
            canvas.create_line(rail_l, child_mids[i], cl, child_mids[i], fill="#475569", width=2)
            canvas.create_line(cl + cw, child_mids[i], rail_r, child_mids[i], fill="#475569", width=2)


# ==========================================
# FRAME KOMPONENTEN
# ==========================================

def _make_entry_cell(parent, bg, on_return, on_keypress):
    cell = tk.Frame(parent, bg=bg)
    e = tk.Entry(cell, width=10, justify="right", font=("Segoe UI", 10),
                 bg=bg, relief=tk.FLAT)
    e.config(highlightbackground="#cbd5e1", highlightthickness=1)
    e.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
    if on_return:
        e.bind("<Return>", on_return)
    if on_keypress:
        e.bind("<KeyPress>", on_keypress)
    return cell, e


class BaukastenFrame(tk.Frame):
    def __init__(self, parent, app_ref=None):
        super().__init__(parent, bg="#f0f4f8")
        self._app_ref       = app_ref
        self._nodes         = []
        self._leaf_nodes    = []
        self._selected      = set()
        self._hit_map       = {}
        self._leaf_hit_map  = {}
        self._table_rows    = {}
        self._gesamt_entries  = {}
        self._history       = []
        self._active_popup  = None
        self._build_ui()

    def _sf(self):
        return self._app_ref.sig_figs_var.get() if self._app_ref else 4

    def _build_ui(self):
        top = tk.Frame(self, bg="#e8eef4", pady=8, padx=12)
        top.pack(fill=tk.X)
        tk.Label(top, text="Anzahl Widerstände:", bg="#e8eef4",
                 font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        self._spin = tk.Spinbox(top, from_=1, to=15, width=4, font=("Segoe UI", 11))
        self._spin.delete(0, tk.END); self._spin.insert(0, "5")
        self._spin.pack(side=tk.LEFT, padx=(4, 16))
        tk.Label(top, text="R-Wert [Ω]:", bg="#e8eef4",
                 font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        self._r_entry = tk.Entry(top, width=8, font=("Segoe UI", 11), justify="right")
        self._r_entry.insert(0, "100")
        self._r_entry.pack(side=tk.LEFT, padx=(4, 6))
        btn_neu = tk.Button(top, text="↺  Neu erstellen", command=self._reset,
                  bg="#1d4ed8", fg="white", font=("Segoe UI", 10, "bold"),
                  padx=10, pady=3)
        btn_neu.pack(side=tk.LEFT, padx=6)
        btn_rset = tk.Button(top, text="R-Wert setzen", command=self._set_rval,
                  bg="#92400e", fg="white", font=("Segoe UI", 9),
                  padx=8, pady=3)
        btn_rset.pack(side=tk.LEFT, padx=4)
        _Tooltip(btn_neu,    "Neue Widerstandsmenge erstellen (verwirft aktuelle Eingaben)")
        _Tooltip(btn_rset,   "R-Wert in alle gewählten (oder alle) Widerstände schreiben")

        paned = tk.PanedWindow(self, orient=tk.VERTICAL,
                               sashrelief=tk.RAISED, sashwidth=6,
                               bg="#cbd5e1", handlepad=200, handlesize=14)
        paned.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        top_pane = tk.Frame(paned, bg="#f0f4f8")
        paned.add(top_pane, minsize=80)

        cf = tk.Frame(top_pane, bg="#ffffff", relief=tk.RIDGE, bd=1)
        cf.pack(fill=tk.BOTH, expand=True, pady=(0, 2))
        self._canvas = tk.Canvas(cf, bg="#ffffff", height=210)
        self._canvas.pack(fill=tk.BOTH, expand=True)
        self._canvas.bind("<Button-1>", self._on_click)
        self._canvas.bind("<Configure>", lambda e: self._redraw())

        fb = tk.Frame(top_pane, bg="#eef2ff", pady=4, relief=tk.SUNKEN, bd=1)
        fb.pack(fill=tk.X, pady=2)
        tk.Label(fb, text="Schaltung:", bg="#eef2ff",
                 font=("Segoe UI", 9, "italic")).pack(side=tk.LEFT, padx=10)
        self._lbl_formula = tk.Label(fb, text="—", bg="#eef2ff",
                                      font=("Consolas", 11, "bold"), fg="#1d4ed8")
        self._lbl_formula.pack(side=tk.LEFT, padx=6)

        ab = tk.Frame(top_pane, bg="#f0f4f8", pady=6)
        ab.pack(fill=tk.X)
        btn_par = tk.Button(ab, text="||  Parallel", command=lambda: self._combine('parallel'),
                  bg="#c2410c", fg="white", font=("Segoe UI", 11, "bold"),
                  padx=14, pady=4)
        btn_par.pack(side=tk.LEFT, padx=4)
        btn_ser = tk.Button(ab, text="+  In Reihe", command=lambda: self._combine('series'),
                  bg="#6d28d9", fg="white", font=("Segoe UI", 11, "bold"),
                  padx=14, pady=4)
        btn_ser.pack(side=tk.LEFT, padx=4)
        btn_dis = tk.Button(ab, text="Auflösen", command=self._dissolve,
                  bg="#475569", fg="white", font=("Segoe UI", 10),
                  padx=10, pady=4)
        btn_dis.pack(side=tk.LEFT, padx=4)
        btn_all = tk.Button(ab, text="Alle wählen", command=self._select_all,
                  bg="#334155", fg="white", font=("Segoe UI", 10),
                  padx=10, pady=4)
        btn_all.pack(side=tk.LEFT, padx=4)
        self._btn_undo = tk.Button(ab, text="← Zurück", command=self._undo,
                  bg="#64748b", fg="white", font=("Segoe UI", 10),
                  padx=10, pady=4)
        self._btn_undo.pack(side=tk.LEFT, padx=4)
        _Tooltip(btn_par,         "Ausgewählte Widerstände parallel schalten (mind. 2 auswählen, Ctrl+Klick)")
        _Tooltip(btn_ser,         "Ausgewählte Widerstände in Reihe schalten (mind. 2 auswählen, Ctrl+Klick)")
        _Tooltip(btn_dis,         "Gewählte Gruppe aufbrechen — Elemente wieder einzeln")
        _Tooltip(btn_all,         "Alle Elemente auf dem Canvas auswählen")
        _Tooltip(self._btn_undo,  "Letzte Struktur-Änderung rückgängig machen")

        bot_pane = tk.Frame(paned, bg="#f0f4f8")
        paned.add(bot_pane, minsize=60)

        tbl_outer = tk.LabelFrame(bot_pane,
                                   text=" Werte eingeben ",
                                   bg="#f0f4f8", font=("Segoe UI", 9, "bold"), pady=4, padx=6)
        tbl_outer.pack(fill=tk.BOTH, expand=True, pady=(0, 2))

        tbl_sf = tk.Frame(tbl_outer, bg="#ffffff")
        tbl_sf.pack(fill=tk.BOTH, expand=True)
        vsb = tk.Scrollbar(tbl_sf, orient=tk.VERTICAL)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._tbl_canvas = tk.Canvas(tbl_sf, bg="#ffffff",
                                      yscrollcommand=vsb.set, highlightthickness=0)
        self._tbl_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.config(command=self._tbl_canvas.yview)
        self._table_frame = tk.Frame(self._tbl_canvas, bg="#ffffff")
        self._tbl_win = self._tbl_canvas.create_window((0, 0), window=self._table_frame, anchor="nw")
        self._table_frame.bind("<Configure>", self._on_table_configure)
        self._tbl_canvas.bind("<Configure>", self._on_tbl_canvas_configure)

        cb = tk.Frame(bot_pane, bg="#f0fdf4", pady=8, padx=12, relief=tk.SUNKEN, bd=1)
        cb.pack(fill=tk.X)
        tk.Button(cb, text="  BERECHNEN  ", command=self._calculate,
                  bg="#059669", fg="white", font=("Segoe UI", 13, "bold"),
                  pady=5).pack(side=tk.LEFT)
        tk.Button(cb, text="Tabelle leeren", command=self._clear_table,
                  bg="#dc2626", fg="white", font=("Segoe UI", 10),
                  padx=8, pady=5).pack(side=tk.LEFT, padx=12)
        self._lbl_result = tk.Label(cb, text="Ersatzwiderstand:  —",
                                     font=("Consolas", 13, "bold"),
                                     bg="#f0fdf4", fg="#065f46")
        self._lbl_result.pack(side=tk.LEFT, padx=20)
        tk.Button(cb, text="⎘", command=self._copy_result,
                  bg="#64748b", fg="white", font=("Segoe UI", 11),
                  padx=6, pady=5).pack(side=tk.LEFT)

    def _on_table_configure(self, event):
        self._tbl_canvas.configure(scrollregion=self._tbl_canvas.bbox("all"))

    def _on_tbl_canvas_configure(self, event):
        self._tbl_canvas.itemconfig(self._tbl_win, width=event.width)

    def _build_table(self):
        self._close_popup()
        for w in self._table_frame.winfo_children(): w.destroy()
        self._table_rows     = {}
        self._gesamt_entries = {}
        headers = ["Bauteil", "U [V]", "I [A]", "R [Ω]", "P [W]"]
        for col, h in enumerate(headers):
            tk.Label(self._table_frame, text=h, font=("Segoe UI", 10, "bold"),
                     bg="#1e293b", fg="white", pady=4
                     ).grid(row=0, column=col, sticky="nsew", padx=1, pady=1)
            self._table_frame.grid_columnconfigure(col, weight=1)
        all_entries = []
        tk.Label(self._table_frame, text="Gesamt", font=("Segoe UI", 10, "bold"),
                 bg="#e2e8f0", pady=4).grid(row=1, column=0, sticky="nsew", padx=1, pady=1)
        for col, k in enumerate(['U', 'I', 'R', 'P']):
            cell, e = _make_entry_cell(self._table_frame, "#f1f5f9",
                                       lambda ev: self._calculate(),
                                       None)
            cell.grid(row=1, column=col + 1, sticky="nsew", padx=1, pady=1)
            self._gesamt_entries[k] = e
            all_entries.append(e)
        for row_idx, node in enumerate(self._leaf_nodes):
            row = row_idx + 2
            bg  = "#f8fafc" if row_idx % 2 == 0 else "#ffffff"
            tk.Label(self._table_frame, text=node.label, font=("Segoe UI", 10),
                     bg=bg, pady=4).grid(row=row, column=0, sticky="nsew", padx=1, pady=1)
            entries = {}
            for col, k in enumerate(['U', 'I', 'R', 'P']):
                cell, e = _make_entry_cell(
                    self._table_frame, bg,
                    lambda ev: self._calculate(),
                    None)
                e.bind("<KeyPress>", lambda ev, ent=e: ent.config(fg="black", font=("Segoe UI", 10)))
                cell.grid(row=row, column=col + 1, sticky="nsew", padx=1, pady=1)
                entries[k] = e
                all_entries.append(e)
            self._table_rows[node] = entries
        for i, e in enumerate(all_entries):
            nxt = all_entries[(i + 1) % len(all_entries)]
            e.bind("<Tab>", lambda ev, n=nxt: (n.focus_set(), n.selection_range(0, tk.END), "break")[2])

    def _parse_r(self):
        try:
            return float(self._r_entry.get().replace(',', '.'))
        except (ValueError, TypeError): return None

    def _reset(self):
        try: n = max(1, min(15, int(self._spin.get())))
        except ValueError: n = 5
        r = self._parse_r()
        self._history    = []
        self._leaf_nodes = [CircuitNode('R', label=f'R{i+1}', r_val=r) for i in range(n)]
        self._nodes      = list(self._leaf_nodes)
        self._selected   = set()
        self._build_table()
        if r is not None:
            for node in self._leaf_nodes:
                self._table_rows[node]['R'].insert(0, str(int(r) if r == int(r) else r))
        self._lbl_result.config(text="Ersatzwiderstand:  —")
        self._redraw()

    def _set_rval(self):
        r = self._parse_r()
        if r is None:
            messagebox.showerror("Fehler", "Ungültiger R-Wert."); return
        targets = [n for n in self._leaf_nodes if n in self._selected] if self._selected else self._leaf_nodes
        for node in targets:
            node.r_val = r
            if node in self._table_rows:
                e = self._table_rows[node]['R']
                e.delete(0, tk.END); e.insert(0, str(int(r) if r == int(r) else r))
                e.config(fg="black", font=("Segoe UI", 10))
        self._redraw()

    def _combine(self, mode):
        if len(self._selected) < 2:
            messagebox.showinfo("Hinweis", "Mindestens 2 Elemente auswählen."); return
        self._push_history()
        ordered  = [n for n in self._nodes if n in self._selected]
        new_node = CircuitNode(mode)
        for child in ordered:
            if child.type == mode: new_node.children.extend(child.children)
            else:                  new_node.children.append(child)
        new_list, inserted = [], False
        for n in self._nodes:
            if n in self._selected:
                if not inserted: new_list.append(new_node); inserted = True
            else: new_list.append(n)
        self._nodes, self._selected = new_list, {new_node}
        self._redraw()

    def _dissolve(self):
        groups = [n for n in self._selected if n.type != 'R']
        if not groups:
            messagebox.showinfo("Hinweis", "Kein kombiniertes Element gewählt."); return
        self._push_history()
        new_list = []
        for n in self._nodes:
            if n in groups: new_list.extend(n.children)
            else:           new_list.append(n)
        self._nodes, self._selected = new_list, set()
        self._redraw()

    def _select_all(self):
        self._selected = set(self._nodes); self._redraw()

    def _collect_leaves(self):
        result = []
        def _col(node):
            if node.type == 'R': result.append(node)
            else:
                for c in node.children: _col(c)
        for n in self._nodes: _col(n)
        return result

    def _push_history(self):
        node_state = [self._serialize_node(n) for n in self._nodes]
        entry_state = {
            node: {k: e.get() for k, e in self._table_rows[node].items()}
            for node in self._leaf_nodes if node in self._table_rows
        }
        gesamt_state = {k: self._gesamt_entries[k].get() for k in ['U', 'I', 'R', 'P']}
        self._history.append((node_state, entry_state, gesamt_state))

    def _serialize_node(self, node):
        if node.type == 'R': return node
        return (node.type, [self._serialize_node(c) for c in node.children])

    def _deserialize_node(self, s):
        if isinstance(s, CircuitNode): return s
        ntype, children = s
        node = CircuitNode(ntype)
        node.children = [self._deserialize_node(c) for c in children]
        return node

    def _undo(self):
        if not self._history: return
        node_state, entry_state, gesamt_state = self._history.pop()
        self._nodes      = [self._deserialize_node(s) for s in node_state]
        self._leaf_nodes = self._collect_leaves()
        self._selected   = set()
        self._build_table()
        for node in self._leaf_nodes:
            if node in entry_state and node in self._table_rows:
                for k, val in entry_state[node].items():
                    self._table_rows[node][k].delete(0, tk.END)
                    self._table_rows[node][k].insert(0, val)
        for k, val in gesamt_state.items():
            self._gesamt_entries[k].delete(0, tk.END)
            self._gesamt_entries[k].insert(0, val)
        self._redraw()

    def _on_click(self, event):
        items   = self._canvas.find_overlapping(event.x - 2, event.y - 2,
                                                 event.x + 2, event.y + 2)
        clicked      = None
        clicked_leaf = None
        for item in reversed(items):
            if item in self._hit_map:
                clicked      = self._hit_map[item]
                clicked_leaf = self._leaf_hit_map.get(item)   # R-Blattknoten für Popup
                break
        ctrl = bool(event.state & 0x0004)
        if clicked is None:
            if not ctrl: self._selected = set()
            self._close_popup()
        elif ctrl:
            if clicked in self._selected: self._selected.discard(clicked)
            else:                          self._selected.add(clicked)
            self._close_popup()
        else:
            self._selected = {clicked}
            if clicked_leaf is not None:
                self._show_node_popup(clicked_leaf, event)
            else:
                self._close_popup()
        self._redraw()

    def _redraw(self):
        c = self._canvas
        c.delete("all")
        self._hit_map      = {}
        self._leaf_hit_map = {}
        if not self._nodes:
            c.create_text(300, 100, text="Klicke auf '↺ Neu erstellen'",
                           font=("Segoe UI", 13), fill="#bbb")
            self._lbl_formula.config(text="—"); return
        W, H = c.winfo_width() or 750, c.winfo_height() or 210
        GAP = 28
        sizes   = [_measure(n) for n in self._nodes]
        total_w = sum(w for w, _ in sizes) + GAP * (len(self._nodes) - 1)
        x, mid_y = max(20, (W - total_w) // 2), H // 2
        for node in self._nodes:
            w, _ = _measure(node)
            _draw_node(c, node, x, mid_y, self._selected, self._hit_map, 0, node,
                       self._leaf_hit_map)
            x += w + GAP
        if len(self._nodes) == 1:
            self._lbl_formula.config(text=self._nodes[0].formula())
        else:
            self._lbl_formula.config(text="  ,  ".join(n.formula() for n in self._nodes) + "   ← verbinden!")

    def _calculate(self):
        if len(self._nodes) != 1:
            messagebox.showwarning("Nicht fertig", "Alle Elemente müssen verbunden sein."); return
        root = self._nodes[0]

        def clear_vals(n):
            n.vals = {'U': None, 'I': None, 'R': None, 'P': None}
            for ch in n.children: clear_vals(ch)
        clear_vals(root)

        for node in self._leaf_nodes:
            for k in ['U', 'I', 'R', 'P']:
                e = self._table_rows[node][k]
                if e.cget("fg") == "blue":
                    e.delete(0, tk.END)
                    e.config(fg="black", font=("Segoe UI", 10))
        for k in ['U', 'I', 'R', 'P']:
            e = self._gesamt_entries[k]
            if e.cget("fg") == "blue":
                e.delete(0, tk.END)
                e.config(fg="black", font=("Segoe UI", 10))

        self._inputs_snapshot = {}
        for node in self._leaf_nodes:
            entries = self._table_rows[node]
            for k in ['U', 'I', 'R', 'P']:
                node.vals[k] = _read_val(entries[k])
            self._inputs_snapshot[node] = {k: node.vals[k] for k in ['U', 'I', 'R', 'P']}

        gesamt_read = {k: _read_val(self._gesamt_entries[k]) for k in ['U', 'I', 'R', 'P']}
        for k in ['U', 'I', 'R', 'P']:
            if root.vals[k] is None:
                root.vals[k] = gesamt_read[k]
        gesamt_inputs = gesamt_read

        _input_vals  = [node.vals.copy() for node in self._leaf_nodes]
        _input_names = [node.label for node in self._leaf_nodes]
        if any(v is not None for v in gesamt_read.values()):
            _input_vals.append(gesamt_read)
            _input_names.append("Gesamt")
        _run_consistency_check(_input_vals, _input_names)

        solve_baukasten(root)

        sf = self._sf()
        for node in self._leaf_nodes:
            entries = self._table_rows[node]
            orig    = self._inputs_snapshot[node]
            for k in ['U', 'I', 'R', 'P']:
                val = node.vals[k]
                if val is not None and orig[k] is None:
                    entries[k].delete(0, tk.END)
                    entries[k].insert(0, f"{val:.{sf}g}")
                    entries[k].config(fg="blue", font=("Segoe UI", 10, "bold"))

        for k in ['U', 'I', 'R', 'P']:
            val = root.vals[k]
            if val is not None and gesamt_inputs[k] is None:
                self._gesamt_entries[k].delete(0, tk.END)
                self._gesamt_entries[k].insert(0, f"{val:.{sf}g}")
                self._gesamt_entries[k].config(fg="blue", font=("Segoe UI", 10, "bold"))

        # Post-solve-Konsistenz: berechnete Werte prüfen
        _solved_vals  = [node.vals.copy() for node in self._leaf_nodes]
        _solved_names = [node.label      for node in self._leaf_nodes]
        _run_consistency_check(_solved_vals, _solved_names)

        if root.vals['R']:
            self._lbl_result.config(text=f"Ersatzwiderstand:  {root.vals['R']:.{sf}g} Ω")
            for node in self._leaf_nodes:
                if node.vals['R'] is not None: node.r_val = node.vals['R']
            self._redraw()
        else:
            self._lbl_result.config(text="Ersatzwiderstand: (nicht berechenbar)")

    def _clear_table(self):
        for node in self._leaf_nodes:
            if node in self._table_rows:
                for e in self._table_rows[node].values():
                    e.delete(0, tk.END)
                    e.config(fg="black", font=("Segoe UI", 10))
                node.r_val = None
        for e in self._gesamt_entries.values():
            e.delete(0, tk.END)
            e.config(fg="black", font=("Segoe UI", 10))
        self._lbl_result.config(text="Ersatzwiderstand:  —")
        self._redraw()

    def _copy_result(self):
        self.clipboard_clear(); self.clipboard_append(self._lbl_result.cget("text"))

    # ------------------------------------------
    # POPUP-METHODEN (schwebendes Eingabe-Fenster)
    # ------------------------------------------

    def _close_popup(self):
        if self._active_popup is None:
            return
        popup, node, popup_entries = self._active_popup
        self._active_popup = None          # Vor destroy setzen → verhindert Re-Entry
        try:
            popup.destroy()
        except tk.TclError:
            pass

    def _show_node_popup(self, node, event):
        self._close_popup()
        canvas = self._canvas

        # Canvas-Item für diesen R-Blattknoten suchen
        item_id = next((iid for iid, n in self._leaf_hit_map.items() if n is node), None)
        if item_id is None:
            return
        x1, y1, x2, y2 = canvas.bbox(item_id)

        # Popup aufbauen (zuerst versteckt, zum Messen)
        popup = tk.Toplevel(self)
        popup.overrideredirect(True)
        popup.configure(bg="#94a3b8")      # Schattenfarbe als Hintergrund
        popup.withdraw()

        # Hauptrahmen (grauer bg zeigt 2px rechts+unten → Schatten-Effekt)
        main = tk.Frame(popup, bg="#f0f4f8", relief=tk.SOLID, bd=1)
        main.pack(padx=(0, 2), pady=(0, 2))

        # Header mit Widerstandsname
        tk.Label(main, text=node.label, bg="#1e293b", fg="white",
                 font=("Segoe UI", 10, "bold"), pady=5, padx=10,
                 anchor="w").pack(fill=tk.X)

        # Eingabefelder U, I, R, P
        ef = tk.Frame(main, bg="#f0f4f8", padx=8, pady=6)
        ef.pack(fill=tk.X)
        popup_entries = {}
        for k, lbl_text in [("U", "U [V]"), ("I", "I [A]"), ("R", "R [Ω]"), ("P", "P [W]")]:
            row = tk.Frame(ef, bg="#f0f4f8")
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=lbl_text, width=7, anchor="w",
                     bg="#f0f4f8", font=("Segoe UI", 10)).pack(side=tk.LEFT)
            e = tk.Entry(row, width=10, justify="right", font=("Segoe UI", 10))
            e.config(highlightbackground="#cbd5e1", highlightthickness=1)
            e.pack(side=tk.LEFT, padx=2)
            popup_entries[k] = e
            # Vorausfüllen aus Tabelle (inkl. Farbe)
            if node in self._table_rows:
                te  = self._table_rows[node][k]
                val = te.get()
                if val:
                    e.insert(0, val)
                fg  = te.cget("fg")
                fnt = ("Segoe UI", 10, "bold") if fg == "blue" else ("Segoe UI", 10)
                e.config(fg=fg, font=fnt)

        # Berechnen-Button
        bf = tk.Frame(main, bg="#f0f4f8", pady=4, padx=8)
        bf.pack(fill=tk.X)
        tk.Button(bf, text="Berechnen", bg="#059669", fg="white",
                  font=("Segoe UI", 10, "bold"),
                  command=lambda: self._popup_calculate(node, popup_entries)
                  ).pack(fill=tk.X)

        # Tastenbindungen
        for k, e in popup_entries.items():
            e.bind("<KeyRelease>",
                   lambda ev, _k=k, _e=e: self._sync_popup_to_table(node, _k, _e))
            e.bind("<Return>",
                   lambda ev: self._popup_calculate(node, popup_entries))
        popup.bind("<Escape>",   lambda ev: self._close_popup())
        popup.bind("<FocusOut>", lambda ev: self._on_popup_focusout(popup))

        # Größe messen, dann positionieren
        popup.update_idletasks()
        pw = popup.winfo_reqwidth()
        ph = popup.winfo_reqheight()

        cx_root = canvas.winfo_rootx()
        cy_root = canvas.winfo_rooty()
        rx = cx_root + x1
        ry = cy_root + y1 - ph - 4        # 4px Abstand über dem Rechteck

        sw = canvas.winfo_screenwidth()
        sh = canvas.winfo_screenheight()
        if rx + pw > sw: rx = max(0, sw - pw)
        if rx < 0:       rx = 0
        if ry < 0:       ry = cy_root + y2 + 4   # Falls kein Platz oben → unten

        popup.geometry(f"+{rx}+{ry}")
        popup.deiconify()
        popup.lift()
        popup_entries['U'].focus_set()

        self._active_popup = (popup, node, popup_entries)

    def _popup_calculate(self, node, popup_entries):
        self._calculate()
        if self._active_popup is not None and self._active_popup[1] is node:
            self._sync_table_to_popup(node, self._active_popup[2])

    def _sync_popup_to_table(self, node, key, popup_entry):
        """Popup-Eingabe → Tabellen-Entry bei jedem Tastendruck übernehmen."""
        if node not in self._table_rows:
            return
        table_e = self._table_rows[node][key]
        val = popup_entry.get()
        table_e.delete(0, tk.END)
        table_e.insert(0, val)
        table_e.config(fg="black", font=("Segoe UI", 10))

    def _sync_table_to_popup(self, node, popup_entries):
        """Tabellen-Entries → Popup-Felder nach _calculate() aktualisieren."""
        if node not in self._table_rows:
            return
        for k, popup_e in popup_entries.items():
            te  = self._table_rows[node][k]
            val = te.get()
            fg  = te.cget("fg")
            fnt = ("Segoe UI", 10, "bold") if fg == "blue" else ("Segoe UI", 10)
            popup_e.delete(0, tk.END)
            popup_e.insert(0, val)
            popup_e.config(fg=fg, font=fnt)

    def _on_popup_focusout(self, popup):
        self.after(100, lambda: self._check_popup_focus(popup))

    def _check_popup_focus(self, popup):
        """Popup schließen, wenn es keinen Fokus mehr hält."""
        if self._active_popup is None or self._active_popup[0] is not popup:
            return
        try:
            fw = popup.focus_get()
            if fw is None:
                self._close_popup()
        except tk.TclError:
            self._close_popup()


# ==========================================
# FARBCODE-FRAME
# ==========================================

def _farbe_info(name):
    for f in FARBEN:
        if f[0] == name:
            return f
    return None


class FarbcodeFrame(tk.Frame):
    def __init__(self, parent, app_ref=None):
        super().__init__(parent, bg="#f0f4f8")
        self._app_ref  = app_ref
        self._direction = tk.StringVar(value="farbe_zu_wert")
        self._v2f_colors = []
        self._build_ui()

    def _sf(self):
        return self._app_ref.sig_figs_var.get() if self._app_ref else 4

    def _build_ui(self):
        top = tk.Frame(self, bg="#e8eef4", pady=8, padx=12)
        top.pack(fill=tk.X)
        tk.Label(top, text="Richtung:", bg="#e8eef4",
                 font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        tk.Radiobutton(top, text="Farbe → Wert", variable=self._direction,
                       value="farbe_zu_wert", bg="#e8eef4", font=("Segoe UI", 10),
                       command=self._switch_dir).pack(side=tk.LEFT, padx=10)
        tk.Radiobutton(top, text="Wert → Farbe", variable=self._direction,
                       value="wert_zu_farbe", bg="#e8eef4", font=("Segoe UI", 10),
                       command=self._switch_dir).pack(side=tk.LEFT, padx=10)

        self._panel_f2v = tk.Frame(self, bg="#f0f4f8")
        self._panel_v2f = tk.Frame(self, bg="#f0f4f8")
        self._build_farbe_zu_wert()
        self._build_wert_zu_farbe()
        self._switch_dir()

    def _switch_dir(self):
        self._panel_f2v.pack_forget()
        self._panel_v2f.pack_forget()
        if self._direction.get() == "farbe_zu_wert":
            self._panel_f2v.pack(fill=tk.BOTH, expand=True)
        else:
            self._panel_v2f.pack(fill=tk.BOTH, expand=True)

    def _build_farbe_zu_wert(self):
        p = self._panel_f2v
        preview_outer = tk.Frame(p, bg="#ffffff", relief=tk.RIDGE, bd=1)
        preview_outer.pack(fill=tk.X, padx=20, pady=(12, 4))
        tk.Label(preview_outer, text="Vorschau Widerstand", bg="#ffffff",
                 font=("Segoe UI", 8, "italic"), fg="#888").pack(anchor="w", padx=8)
        self._f2v_canvas = tk.Canvas(preview_outer, bg="#f8fafc", height=90,
                                      highlightthickness=0)
        self._f2v_canvas.pack(fill=tk.X, padx=8, pady=(0, 8))
        self._f2v_canvas.bind("<Configure>", lambda e: self._redraw_f2v())

        dd_frame = tk.LabelFrame(p, text=" Farbringe auswählen ",
                                  bg="#f0f4f8", padx=15, pady=10,
                                  font=("Segoe UI", 9, "bold"))
        dd_frame.pack(fill=tk.X, padx=20, pady=4)

        digit_names = [f[0] for f in FARBEN if f[3] is not None]
        mult_names  = [f[0] for f in FARBEN if f[4] is not None]
        tol_names   = ["(kein)"] + [f[0] for f in FARBEN if f[5] is not None]

        ring_specs = [
            ("Ring 1  (1. Ziffer):",      digit_names, "Braun"),
            ("Ring 2  (2. Ziffer):",      digit_names, "Schwarz"),
            ("Ring 3  (3. Ziffer):",      digit_names, "Schwarz"),
            ("Ring 4  (Multiplikator):",  mult_names,  "Schwarz"),
            ("Ring 5  (Toleranz, opt.):", tol_names,   "(kein)"),
        ]
        self._ring_vars = []
        for label_txt, vals, default in ring_specs:
            row = tk.Frame(dd_frame, bg="#f0f4f8")
            row.pack(fill=tk.X, pady=3)
            tk.Label(row, text=label_txt, width=26, anchor="w",
                     bg="#f0f4f8", font=("Segoe UI", 10)).pack(side=tk.LEFT)
            var = tk.StringVar(value=default)
            cb = ttk.Combobox(row, values=vals, textvariable=var,
                              state="readonly", width=14)
            cb.pack(side=tk.LEFT, padx=4)
            fi = _farbe_info(default)
            bg_hex = fi[1] if fi else "#ffffff"
            color_patch = tk.Label(row, text="      ", bg=bg_hex,
                                   relief=tk.RAISED, bd=2, width=5)
            color_patch.pack(side=tk.LEFT, padx=4)
            var.trace_add("write",
                lambda *a, v=var, cp=color_patch: self._on_ring_change(v, cp))
            self._ring_vars.append((var, color_patch))

        btn_row = tk.Frame(p, bg="#f0fdf4", pady=8, padx=20, relief=tk.SUNKEN, bd=1)
        btn_row.pack(fill=tk.X, padx=20, pady=6)
        tk.Button(btn_row, text="  BERECHNEN  ", command=self._calc_f2v,
                  bg="#059669", fg="white", font=("Segoe UI", 12, "bold"), pady=4).pack(side=tk.LEFT)
        self._f2v_result = tk.Label(btn_row, text="Widerstandswert:  —",
                                     font=("Consolas", 13, "bold"),
                                     bg="#f0fdf4", fg="#065f46")
        self._f2v_result.pack(side=tk.LEFT, padx=20)

    def _on_ring_change(self, var, color_patch):
        name = var.get()
        fi = _farbe_info(name)
        color_patch.config(bg=fi[1] if fi else "#ffffff")
        self._redraw_f2v()

    def _redraw_f2v(self):
        c = self._f2v_canvas
        c.delete("all")
        W = c.winfo_width() or 500
        H = 90
        ring_names = []
        for i, (var, _) in enumerate(self._ring_vars):
            name = var.get()
            if i == 4 and name == "(kein)":
                continue
            ring_names.append(name)
        if not ring_names: return
        n = len(ring_names)
        rw, rh = 52, 62
        gap = 18
        total_w = n * rw + (n - 1) * gap
        body_pad = 28
        x0 = max(10, (W - total_w) // 2)
        y0 = (H - rh) // 2
        c.create_line(0, H // 2, x0 - body_pad, H // 2, fill="#64748b", width=2)
        c.create_line(x0 + total_w + body_pad, H // 2, W, H // 2, fill="#64748b", width=2)
        c.create_rectangle(x0 - body_pad, y0 + 4, x0 + total_w + body_pad, y0 + rh - 4,
                            fill="#fef3c7", outline="#78350f", width=2)
        for i, name in enumerate(ring_names):
            fi = _farbe_info(name)
            bg_hex = fi[1] if fi else "#94a3b8"
            fg_hex = fi[2] if fi else "#000000"
            x = x0 + i * (rw + gap)
            c.create_rectangle(x, y0, x + rw, y0 + rh, fill=bg_hex, outline="#333333", width=1)
            short = name[:3] if name != "(kein)" else "—"
            c.create_text(x + rw // 2, y0 + rh // 2 - 8,
                          text=short, font=("Segoe UI", 7, "bold"), fill=fg_hex)
            fi2 = _farbe_info(name)
            if fi2:
                if fi2[3] is not None:   info = str(fi2[3])
                elif fi2[4] is not None: info = f"×{fi2[4]:g}"
                else:                    info = ""
                c.create_text(x + rw // 2, y0 + rh // 2 + 10,
                              text=info, font=("Segoe UI", 7), fill=fg_hex)

    def _calc_f2v(self):
        names = [var.get() for var, _ in self._ring_vars]
        infos = [_farbe_info(n) for n in names[:4]]
        if any(fi is None for fi in infos):
            self._f2v_result.config(text="Fehler: unbekannte Farbe"); return
        f1, f2, f3, f4 = infos
        if any(fi[3] is None for fi in [f1, f2, f3]):
            self._f2v_result.config(text="Fehler: Ringe 1-3 brauchen Ziffernfarbe"); return
        if f4[4] is None:
            self._f2v_result.config(text="Fehler: Ring 4 braucht Multiplikator-Farbe"); return
        val = (f1[3] * 100 + f2[3] * 10 + f3[3]) * f4[4]
        sf  = self._sf()
        disp, unit = _format_with_unit(val, sf)
        tol_name = names[4]
        tol_str  = ""
        if tol_name != "(kein)":
            f5 = _farbe_info(tol_name)
            if f5 and f5[5]:
                tol_str = f"  {f5[5]}"
                pct = float(f5[5].strip("±%")) / 100
                lo, hi = val * (1 - pct), val * (1 + pct)
                d_lo, u_lo = _format_with_unit(lo, sf)
                d_hi, u_hi = _format_with_unit(hi, sf)
                self._f2v_result.config(
                    text=f"R = {disp} {unit}Ω{tol_str}   [{d_lo} {u_lo}Ω … {d_hi} {u_hi}Ω]")
                self._redraw_f2v(); return
        self._f2v_result.config(text=f"R = {disp} {unit}Ω{tol_str}")
        self._redraw_f2v()

    def _build_wert_zu_farbe(self):
        p = self._panel_v2f
        inp = tk.LabelFrame(p, text=" Widerstandswert eingeben ",
                             bg="#f0f4f8", padx=15, pady=10, font=("Segoe UI", 9, "bold"))
        inp.pack(fill=tk.X, padx=20, pady=12)
        row = tk.Frame(inp, bg="#f0f4f8")
        row.pack(fill=tk.X)
        tk.Label(row, text="R [Ω]:", font=("Segoe UI", 11, "bold"),
                 bg="#f0f4f8").pack(side=tk.LEFT, padx=(0, 6))
        cell, self._v2f_entry = _make_entry_cell(row, "#f0f4f8", lambda ev: self._calc_v2f(), None)
        cell.pack(side=tk.LEFT)
        tk.Button(row, text="  BERECHNEN  ", command=self._calc_v2f,
                  bg="#059669", fg="white", font=("Segoe UI", 11, "bold"),
                  padx=8, pady=3).pack(side=tk.LEFT, padx=14)
        canvas_frame = tk.Frame(p, bg="#ffffff", relief=tk.RIDGE, bd=1)
        canvas_frame.pack(fill=tk.X, padx=20, pady=4)
        tk.Label(canvas_frame, text="Farbcode-Darstellung (4-Band)", bg="#ffffff",
                 font=("Segoe UI", 8, "italic"), fg="#888").pack(anchor="w", padx=8)
        self._v2f_canvas = tk.Canvas(canvas_frame, bg="#f8fafc", height=130, highlightthickness=0)
        self._v2f_canvas.pack(fill=tk.X, padx=8, pady=(0, 8))
        self._v2f_canvas.bind("<Configure>", lambda e: self._redraw_v2f())
        self._v2f_info = tk.Label(p, text="", font=("Consolas", 10), bg="#f0f4f8",
                                   fg="#1d4ed8", justify=tk.LEFT)
        self._v2f_info.pack(padx=20, anchor="w")

    def _encode_5band(self, val):
        if val <= 0: return None
        try:    log = math.log10(val)
        except: return None
        exp = math.floor(log) - 2
        mult = 10.0 ** exp
        digits = round(val / mult)
        if digits >= 1000: digits = round(digits / 10); mult *= 10
        elif digits < 100: digits = round(digits * 10); mult /= 10
        valid = any(f[4] is not None and abs(f[4] - mult) / max(abs(mult), 1e-20) < 0.001
                    for f in FARBEN)
        if not valid: return None
        return digits // 100, (digits // 10) % 10, digits % 10, mult

    def _calc_v2f(self):
        val = _read_val(self._v2f_entry)
        if val is None or val <= 0:
            messagebox.showerror("Fehler", "Bitte einen gültigen positiven Widerstandswert eingeben.")
            return
        result = self._encode_5band(val)
        if result is None:
            messagebox.showerror("Fehler", "Wert außerhalb des darstellbaren Bereichs (1 Ω … 999 GΩ).")
            return
        d1, d2, d3, mult = result

        def find_digit(d):
            for f in FARBEN:
                if f[3] == d: return f
        def find_mult(m):
            for f in FARBEN:
                if f[4] is not None and abs(f[4] - m) / max(abs(m), 1e-20) < 0.001: return f

        rings = [find_digit(d1), find_digit(d2), find_digit(d3), find_mult(mult)]
        if any(r is None for r in rings):
            messagebox.showerror("Fehler", "Farbzuordnung fehlgeschlagen."); return
        self._v2f_colors = rings
        sf = self._sf()
        disp, unit = _format_with_unit(val, sf)
        names = [f[0] for f in rings]
        self._v2f_info.config(
            text=f"R = {disp} {unit}Ω\n"
                 f"Ringe: {names[0]} | {names[1]} | {names[2]} | {names[3]}\n"
                 f"= ({d1}{d2}{d3}) × {mult:g} Ω")
        self._redraw_v2f()

    def _redraw_v2f(self):
        c = self._v2f_canvas
        c.delete("all")
        W = c.winfo_width() or 600
        H = 130
        if not self._v2f_colors:
            c.create_text(W // 2, H // 2, text="Wert eingeben und BERECHNEN drücken",
                          font=("Segoe UI", 11), fill="#aaa"); return
        n = len(self._v2f_colors)
        rw, rh = 68, 88
        gap = 22
        total_w = n * rw + (n - 1) * gap
        body_pad = 36
        x0 = max(10, (W - total_w) // 2)
        y0 = (H - rh) // 2
        c.create_line(0, H // 2, x0 - body_pad, H // 2, fill="#64748b", width=3)
        c.create_line(x0 + total_w + body_pad, H // 2, W, H // 2, fill="#64748b", width=3)
        c.create_rectangle(x0 - body_pad, y0 + 4, x0 + total_w + body_pad, y0 + rh - 4,
                            fill="#fef3c7", outline="#78350f", width=3)
        ring_labels = ["1. Ziffer", "2. Ziffer", "3. Ziffer", "Multiplik."]
        for i, fi in enumerate(self._v2f_colors):
            x = x0 + i * (rw + gap)
            bg_h, fg_h = fi[1], fi[2]
            c.create_rectangle(x, y0, x + rw, y0 + rh, fill=bg_h, outline="#222", width=1)
            c.create_text(x + rw // 2, y0 + 14, text=fi[0], font=("Segoe UI", 8, "bold"), fill=fg_h)
            c.create_line(x, y0 + 24, x + rw, y0 + 24, fill=fg_h, width=1, dash=(3, 3))
            info_top = str(fi[3]) if fi[3] is not None else (f"×{fi[4]:g}" if fi[4] is not None else "")
            c.create_text(x + rw // 2, y0 + rh // 2 + 8,
                          text=info_top, font=("Segoe UI", 9, "bold"), fill=fg_h)
            c.create_text(x + rw // 2, H - 6, text=ring_labels[i], font=("Segoe UI", 7), fill="#475569")

    def calculate(self):
        if self._direction.get() == "farbe_zu_wert": self._calc_f2v()
        else:                                         self._calc_v2f()


# ==========================================
# PRÄFIX-UMRECHNER
# ==========================================

class PraefixFrame(tk.Frame):
    PREFIXES = [
        ("Tera",  "T",  12 ),
        ("Giga",  "G",  9  ),
        ("Mega",  "M",  6  ),
        ("Kilo",  "k",  3  ),
        ("Basis", "—",  0  ),
        ("Milli", "m",  -3 ),
        ("Mikro", "µ",  -6 ),
        ("Nano",  "n",  -9 ),
        ("Piko",  "p",  -12),
        ("Femto", "f",  -15),
    ]

    def __init__(self, parent, app_ref=None):
        super().__init__(parent, bg="#f0f4f8")
        self._entries = {}
        self._build_ui()

    @staticmethod
    def _sup(exp):
        sup_map = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")
        if exp == 0:
            return "× 1"
        return f"× 10{str(exp).translate(sup_map)}"

    def _build_ui(self):
        outer = tk.Frame(self, bg="#f0f4f8", padx=40, pady=16)
        outer.pack(fill=tk.BOTH, expand=True)

        box = tk.LabelFrame(
            outer,
            text=" Einheitenpräfixe ",
            bg="white", padx=14, pady=10, font=("Segoe UI", 10, "bold"))
        box.pack(fill=tk.X)
        box.columnconfigure(3, weight=1)

        for col, (h, w, anchor) in enumerate([
            ("Präfix", 14, "w"), ("Symbol", 7, "center"),
            ("Faktor", 10, "e"), ("Wert", 18, "e")
        ]):
            tk.Label(box, text=h, bg="#1e293b", fg="white",
                     font=("Segoe UI", 10, "bold"), width=w, pady=4, anchor=anchor
                     ).grid(row=0, column=col, sticky="nsew", padx=1, pady=(0, 4))

        for row_idx, (name, symbol, exp) in enumerate(self.PREFIXES):
            bg = "#f8fafc" if row_idx % 2 == 0 else "#ffffff"
            r = row_idx + 1
            tk.Label(box, text=name, bg=bg, anchor="w",
                     font=("Segoe UI", 10), width=14, padx=6
                     ).grid(row=r, column=0, sticky="nsew", padx=1, pady=2)
            tk.Label(box, text=symbol, bg=bg, anchor="center",
                     font=("Consolas", 11, "bold"), fg="#1d4ed8", width=7
                     ).grid(row=r, column=1, sticky="nsew", padx=1, pady=2)
            tk.Label(box, text=self._sup(exp), bg=bg, anchor="e",
                     font=("Consolas", 10), fg="#475569", width=10, padx=6
                     ).grid(row=r, column=2, sticky="nsew", padx=1, pady=2)
            e = tk.Entry(box, width=20, justify="right", font=("Segoe UI", 10),
                         bg=bg, relief=tk.FLAT)
            e.config(highlightbackground="#cbd5e1", highlightthickness=1)
            e.grid(row=r, column=3, sticky="ew", padx=(4, 2), pady=2)
            e.bind("<Return>", lambda ev, s=symbol: self._calc_from(s))
            e.bind("<KeyPress>", lambda ev, ent=e: ent.config(fg="black", font=("Segoe UI", 10)))
            self._entries[symbol] = e

        btn_f = tk.Frame(outer, bg="#f0f4f8", pady=10)
        btn_f.pack(fill=tk.X)
        tk.Button(btn_f, text="  BERECHNEN  ", command=self._berechnen,
                  bg="#059669", fg="white", font=("Segoe UI", 12, "bold"),
                  width=15, pady=5).pack(side=tk.LEFT)
        tk.Button(btn_f, text="Leeren", command=self._clear,
                  bg="#dc2626", fg="white", font=("Segoe UI", 10),
                  padx=12, pady=5).pack(side=tk.LEFT, padx=12)
        self._lbl_status = tk.Label(btn_f, text="",
                                     font=("Segoe UI", 10), bg="#f0f4f8", fg="#64748b")
        self._lbl_status.pack(side=tk.LEFT)

    def _berechnen(self):
        for _, symbol, _ in self.PREFIXES:
            e = self._entries[symbol]
            if e.cget("fg") != "blue" and e.get().strip():
                self._calc_from(symbol)
                return
        self._lbl_status.config(text="Bitte einen Wert eingeben.", fg="#c2410c")

    def _calc_from(self, symbol):
        raw = self._entries[symbol].get().strip()
        if not raw:
            self._clear()
            return
        val = parse_value(raw)
        if val is None:
            self._lbl_status.config(text="Ungültige Eingabe.", fg="#dc2626")
            return
        exp = next(e for _, s, e in self.PREFIXES if s == symbol)
        base = val * (10 ** exp)
        self._entries[symbol].config(fg="black", font=("Segoe UI", 10))
        self._fill_from_base(base, skip=symbol)

    def _fill_from_base(self, base, skip=None):
        for name, symbol, exp in self.PREFIXES:
            if symbol == skip:
                continue
            e = self._entries[symbol]
            result = base / (10 ** exp)
            e.delete(0, tk.END)
            e.insert(0, f"{result:.10g}")
            e.config(fg="blue", font=("Segoe UI", 10, "bold"))
        self._lbl_status.config(text=f"✓  Basiswert: {base:.10g}", fg="#059669")

    def _clear(self):
        for e in self._entries.values():
            e.delete(0, tk.END)
            e.config(fg="black", font=("Segoe UI", 10))
        self._lbl_status.config(text="", fg="#64748b")


# ==========================================
# SZENARIEN-VERGLEICH (VISUELL)
# ==========================================

class SzenarienVisuelFrame(tk.Frame):
    """Visueller Szenarien-Vergleich: selbes Baukasten-Canvas, aber doppelte
    Wertetabelle (Szenario 1 | Szenario 2) mit R-Kopplung und Gleichungssystem-Löser."""

    def __init__(self, parent, app_ref=None):
        super().__init__(parent, bg="#f0f4f8")
        self._app_ref      = app_ref
        self._nodes        = []
        self._leaf_nodes   = []
        self._selected     = set()
        self._hit_map      = {}
        self._table_rows   = {}   # node -> {'ents_sz1':{k:e}, 'ents_sz2':{k:e}, 'coupled':BoolVar, 'couple_btn':btn}
        self._gesamt_sz1   = {}   # k -> entry
        self._gesamt_sz2   = {}
        self._history      = []
        self._ug_linked    = tk.BooleanVar(value=False)
        self._lbl_result   = None
        self._build_ui()

    def _sf(self):
        return self._app_ref.sig_figs_var.get() if self._app_ref else 4

    # ── UI ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        top = tk.Frame(self, bg="#e8eef4", pady=8, padx=12)
        top.pack(fill=tk.X)
        tk.Label(top, text="Anzahl Widerstände:", bg="#e8eef4",
                 font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        self._spin = tk.Spinbox(top, from_=1, to=15, width=4, font=("Segoe UI", 11))
        self._spin.delete(0, tk.END); self._spin.insert(0, "3")
        self._spin.pack(side=tk.LEFT, padx=(4, 16))
        tk.Label(top, text="R-Wert [Ω]:", bg="#e8eef4",
                 font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        self._r_entry = tk.Entry(top, width=8, font=("Segoe UI", 11), justify="right")
        self._r_entry.insert(0, "100")
        self._r_entry.pack(side=tk.LEFT, padx=(4, 6))
        tk.Button(top, text="↺  Neu erstellen", command=self._reset,
                  bg="#1d4ed8", fg="white", font=("Segoe UI", 10, "bold"),
                  padx=10, pady=3).pack(side=tk.LEFT, padx=6)
        tk.Button(top, text="R-Wert setzen", command=self._set_rval,
                  bg="#92400e", fg="white", font=("Segoe UI", 9),
                  padx=8, pady=3).pack(side=tk.LEFT, padx=4)
        chk_ug = tk.Checkbutton(top, text="Ug gleich", variable=self._ug_linked,
                       bg="#e8eef4", font=("Segoe UI", 10, "bold"),
                       fg="#065f46")
        chk_ug.pack(side=tk.LEFT, padx=(20, 4))
        _Tooltip(chk_ug, "Erzwingt gleiche Gesamtspannung in beiden Szenarien\n(Bisektion löst das unbekannte R automatisch)")

        paned = tk.PanedWindow(self, orient=tk.VERTICAL,
                               sashrelief=tk.RAISED, sashwidth=6,
                               bg="#cbd5e1", handlepad=200, handlesize=14)
        paned.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        # ── Canvas pane
        top_pane = tk.Frame(paned, bg="#f0f4f8")
        paned.add(top_pane, minsize=80)
        cf = tk.Frame(top_pane, bg="#ffffff", relief=tk.RIDGE, bd=1)
        cf.pack(fill=tk.BOTH, expand=True, pady=(0, 2))
        self._canvas = tk.Canvas(cf, bg="#ffffff", height=200)
        self._canvas.pack(fill=tk.BOTH, expand=True)
        self._canvas.bind("<Button-1>", self._on_click)
        self._canvas.bind("<Configure>", lambda e: self._redraw())
        fb = tk.Frame(top_pane, bg="#eef2ff", pady=4, relief=tk.SUNKEN, bd=1)
        fb.pack(fill=tk.X, pady=2)
        tk.Label(fb, text="Schaltung:", bg="#eef2ff",
                 font=("Segoe UI", 9, "italic")).pack(side=tk.LEFT, padx=10)
        self._lbl_formula = tk.Label(fb, text="—", bg="#eef2ff",
                                      font=("Consolas", 11, "bold"), fg="#1d4ed8")
        self._lbl_formula.pack(side=tk.LEFT, padx=6)
        ab = tk.Frame(top_pane, bg="#f0f4f8", pady=6)
        ab.pack(fill=tk.X)
        for txt, col, cmd in [
            ("||  Parallel", "#c2410c", lambda: self._combine("parallel")),
            ("+  In Reihe",  "#6d28d9", lambda: self._combine("series")),
            ("Auflösen",     "#475569", self._dissolve),
            ("Alle wählen",  "#334155", self._select_all),
        ]:
            tk.Button(ab, text=txt, command=cmd, bg=col, fg="white",
                      font=("Segoe UI", 10, "bold"), padx=10, pady=4
                      ).pack(side=tk.LEFT, padx=4)
        self._btn_undo = tk.Button(ab, text="← Zurück", command=self._undo,
                                    bg="#64748b", fg="white", font=("Segoe UI", 10),
                                    padx=10, pady=4)
        self._btn_undo.pack(side=tk.LEFT, padx=4)

        # ── Table pane
        bot_pane = tk.Frame(paned, bg="#f0f4f8")
        paned.add(bot_pane, minsize=80)
        tbl_outer = tk.LabelFrame(bot_pane, text=" Werte — Szenario 1 | Szenario 2 ",
                                   bg="#f0f4f8", font=("Segoe UI", 9, "bold"),
                                   pady=4, padx=6)
        tbl_outer.pack(fill=tk.BOTH, expand=True, pady=(0, 2))
        tbl_sf = tk.Frame(tbl_outer, bg="#ffffff")
        tbl_sf.pack(fill=tk.BOTH, expand=True)
        vsb = tk.Scrollbar(tbl_sf, orient=tk.VERTICAL)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._tbl_canvas = tk.Canvas(tbl_sf, bg="#ffffff",
                                      yscrollcommand=vsb.set, highlightthickness=0)
        self._tbl_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.config(command=self._tbl_canvas.yview)
        self._tbl_frame = tk.Frame(self._tbl_canvas, bg="#ffffff")
        self._tbl_win   = self._tbl_canvas.create_window(
            (0, 0), window=self._tbl_frame, anchor="nw")
        self._tbl_frame.bind("<Configure>",
            lambda e: self._tbl_canvas.configure(
                scrollregion=self._tbl_canvas.bbox("all")))
        self._tbl_canvas.bind("<Configure>",
            lambda e: self._tbl_canvas.itemconfig(self._tbl_win, width=e.width))

        cb = tk.Frame(bot_pane, bg="#f0fdf4", pady=8, padx=12, relief=tk.SUNKEN, bd=1)
        cb.pack(fill=tk.X)
        tk.Button(cb, text="  BERECHNEN  ", command=self._calculate,
                  bg="#059669", fg="white", font=("Segoe UI", 13, "bold"),
                  pady=5).pack(side=tk.LEFT)
        tk.Button(cb, text="Tabelle leeren", command=self._clear_table,
                  bg="#dc2626", fg="white", font=("Segoe UI", 10),
                  padx=8, pady=5).pack(side=tk.LEFT, padx=12)
        self._lbl_result = tk.Label(cb, text="",
                                     font=("Consolas", 12, "bold"),
                                     bg="#f0fdf4", fg="#065f46")
        self._lbl_result.pack(side=tk.LEFT, padx=10)

    # ── Table ─────────────────────────────────────────────────────────────
    def _build_table(self):
        for w in self._tbl_frame.winfo_children(): w.destroy()
        self._table_rows   = {}
        self._gesamt_sz1   = {}
        self._gesamt_sz2   = {}

        # Header row 0 — section titles
        tk.Label(self._tbl_frame, text="Bauteil", font=("Segoe UI", 9, "bold"),
                 bg="#1a2332", fg="white", pady=3
                 ).grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        tk.Label(self._tbl_frame, text="← Szenario 1 →",
                 font=("Segoe UI", 9, "bold"), bg="#1d4ed8", fg="white", pady=3
                 ).grid(row=0, column=1, columnspan=4, sticky="nsew", padx=1, pady=1)
        tk.Label(self._tbl_frame, text="R=", font=("Segoe UI", 8, "bold"),
                 bg="#475569", fg="white", pady=3, width=2
                 ).grid(row=0, column=5, sticky="nsew", padx=1, pady=1)
        tk.Label(self._tbl_frame, text="← Szenario 2 →",
                 font=("Segoe UI", 9, "bold"), bg="#065f46", fg="white", pady=3
                 ).grid(row=0, column=6, columnspan=4, sticky="nsew", padx=1, pady=1)

        # Header row 1 — column names
        tk.Label(self._tbl_frame, text="", bg="#1a2332"
                 ).grid(row=1, column=0, sticky="nsew", padx=1)
        tk.Label(self._tbl_frame, text="", bg="#475569"
                 ).grid(row=1, column=5, sticky="nsew", padx=1)
        for ci, h in enumerate(["U [V]", "I [A]", "R [Ω]", "P [W]"]):
            tk.Label(self._tbl_frame, text=h, font=("Segoe UI", 8, "bold"),
                     bg="#1e293b", fg="white", pady=2
                     ).grid(row=1, column=ci+1, sticky="nsew", padx=1)
            tk.Label(self._tbl_frame, text=h, font=("Segoe UI", 8, "bold"),
                     bg="#1e293b", fg="white", pady=2
                     ).grid(row=1, column=ci+6, sticky="nsew", padx=1)

        self._tbl_frame.grid_columnconfigure(0, weight=1, minsize=60)
        self._tbl_frame.grid_columnconfigure(5, weight=0, minsize=26)
        for c in list(range(1, 5)) + list(range(6, 10)):
            self._tbl_frame.grid_columnconfigure(c, weight=2, minsize=56)

        # Gesamt row
        self._add_dual_row("Gesamt", bg="#e2e8f0", is_total=True, grid_row=2)

        # Leaf rows
        for ri, node in enumerate(self._leaf_nodes):
            bg = "#f8fafc" if ri % 2 == 0 else "#ffffff"
            self._add_dual_row(node.label, bg=bg, is_total=False,
                                grid_row=ri + 3, node=node)

    def _add_dual_row(self, label, bg, is_total, grid_row, node=None):
        tk.Label(self._tbl_frame, text=label, font=("Segoe UI", 10),
                 bg=bg, pady=3, anchor="w", padx=4
                 ).grid(row=grid_row, column=0, sticky="nsew", padx=1, pady=1)

        ents_sz1, ents_sz2 = {}, {}
        for ci, k in enumerate(['U', 'I', 'R', 'P']):
            _, e1 = _make_entry_cell(self._tbl_frame, bg,
                                     lambda ev: self._calculate(), None)
            e1.bind("<KeyPress>",
                    lambda ev, e=e1: e.config(fg="black", font=("Segoe UI", 10)))
            _.grid(row=grid_row, column=ci+1, sticky="nsew", padx=1, pady=1)
            ents_sz1[k] = e1

        # Coupling button — only for component rows
        coupled_var = tk.BooleanVar(value=False)
        if is_total:
            tk.Label(self._tbl_frame, text="", bg=bg
                     ).grid(row=grid_row, column=5, sticky="nsew", padx=1, pady=1)
            couple_btn = None
        else:
            couple_btn = tk.Button(self._tbl_frame, text="=",
                                    font=("Segoe UI", 8, "bold"), width=2,
                                    bg="#64748b", fg="white", relief=tk.FLAT)
            couple_btn.grid(row=grid_row, column=5, sticky="nsew", padx=1, pady=1)

            def _toggle(rv=coupled_var, btn=couple_btn):
                rv.set(not rv.get())
                btn.config(bg="#059669" if rv.get() else "#64748b")

            couple_btn.config(command=_toggle)

        for ci, k in enumerate(['U', 'I', 'R', 'P']):
            _, e2 = _make_entry_cell(self._tbl_frame, bg,
                                     lambda ev: self._calculate(), None)
            e2.bind("<KeyPress>",
                    lambda ev, e=e2: e.config(fg="black", font=("Segoe UI", 10)))
            _.grid(row=grid_row, column=ci+6, sticky="nsew", padx=1, pady=1)
            ents_sz2[k] = e2

        if is_total:
            self._gesamt_sz1 = ents_sz1
            self._gesamt_sz2 = ents_sz2
        else:
            self._table_rows[node] = {
                'ents_sz1': ents_sz1, 'ents_sz2': ents_sz2,
                'coupled': coupled_var, 'couple_btn': couple_btn,
            }

    # ── Node management (identical to BaukastenFrame) ─────────────────────
    def _parse_r(self):
        try:    return float(self._r_entry.get().replace(',', '.'))
        except: return None

    def _reset(self):
        try:    n = max(1, min(15, int(self._spin.get())))
        except: n = 3
        r = self._parse_r()
        self._history    = []
        self._leaf_nodes = [CircuitNode('R', label=f'R{i+1}', r_val=r) for i in range(n)]
        self._nodes      = list(self._leaf_nodes)
        self._selected   = set()
        self._build_table()
        if r is not None:
            for node in self._leaf_nodes:
                rv = str(int(r) if r == int(r) else r)
                self._table_rows[node]['ents_sz1']['R'].insert(0, rv)
                self._table_rows[node]['ents_sz2']['R'].insert(0, rv)
        if self._lbl_result: self._lbl_result.config(text="")
        self._redraw()

    def _set_rval(self):
        r = self._parse_r()
        if r is None: messagebox.showerror("Fehler", "Ungültiger R-Wert."); return
        targets = ([n for n in self._leaf_nodes if n in self._selected]
                   if self._selected else self._leaf_nodes)
        rv = str(int(r) if r == int(r) else r)
        for node in targets:
            node.r_val = r
            for sz in ['sz1', 'sz2']:
                e = self._table_rows[node][f'ents_{sz}']['R']
                e.delete(0, tk.END); e.insert(0, rv)
                e.config(fg="black", font=("Segoe UI", 10))
        self._redraw()

    def _combine(self, mode):
        if len(self._selected) < 2:
            messagebox.showinfo("Hinweis", "Mindestens 2 Elemente auswählen."); return
        self._push_history()
        ordered  = [n for n in self._nodes if n in self._selected]
        new_node = CircuitNode(mode)
        for child in ordered:
            if child.type == mode: new_node.children.extend(child.children)
            else:                  new_node.children.append(child)
        new_list, inserted = [], False
        for n in self._nodes:
            if n in self._selected:
                if not inserted: new_list.append(new_node); inserted = True
            else: new_list.append(n)
        self._nodes, self._selected = new_list, {new_node}
        self._redraw()

    def _dissolve(self):
        groups = [n for n in self._selected if n.type != 'R']
        if not groups:
            messagebox.showinfo("Hinweis", "Kein kombiniertes Element gewählt."); return
        self._push_history()
        new_list = []
        for n in self._nodes:
            if n in groups: new_list.extend(n.children)
            else:           new_list.append(n)
        self._nodes, self._selected = new_list, set()
        self._redraw()

    def _select_all(self): self._selected = set(self._nodes); self._redraw()

    def _push_history(self):
        def _ser(n): return n if n.type == 'R' else (n.type, [_ser(c) for c in n.children])
        def _get_ents(node, sz):
            return {k: self._table_rows[node][f'ents_{sz}'][k].get()
                    for k in ['U', 'I', 'R', 'P']}
        self._history.append((
            [_ser(n) for n in self._nodes],
            {node: {'sz1': _get_ents(node, 'sz1'), 'sz2': _get_ents(node, 'sz2')}
             for node in self._leaf_nodes if node in self._table_rows},
            {sz: {k: self._gesamt_sz1[k].get() if sz == 'sz1'
                     else self._gesamt_sz2[k].get()
                  for k in ['U', 'I', 'R', 'P']} for sz in ['sz1', 'sz2']},
        ))

    def _undo(self):
        if not self._history: return
        node_ser, ent_state, gest_state = self._history.pop()

        def _deser(s):
            if isinstance(s, CircuitNode): return s
            ntype, children = s
            node = CircuitNode(ntype)
            node.children = [_deser(c) for c in children]
            return node

        def _collect_leaves(nodes):
            result = []
            def _col(n):
                if n.type == 'R': result.append(n)
                else:
                    for c in n.children: _col(c)
            for n in nodes: _col(n)
            return result

        self._nodes      = [_deser(s) for s in node_ser]
        self._leaf_nodes = _collect_leaves(self._nodes)
        self._selected   = set()
        self._build_table()
        for node in self._leaf_nodes:
            if node in ent_state and node in self._table_rows:
                for sz in ['sz1', 'sz2']:
                    for k, val in ent_state[node][sz].items():
                        self._table_rows[node][f'ents_{sz}'][k].delete(0, tk.END)
                        self._table_rows[node][f'ents_{sz}'][k].insert(0, val)
        for sz, d in gest_state.items():
            g = self._gesamt_sz1 if sz == 'sz1' else self._gesamt_sz2
            for k, val in d.items():
                g[k].delete(0, tk.END); g[k].insert(0, val)
        self._redraw()

    def _on_click(self, event):
        items   = self._canvas.find_overlapping(event.x-2, event.y-2,
                                                 event.x+2, event.y+2)
        clicked = None
        for item in reversed(items):
            if item in self._hit_map: clicked = self._hit_map[item]; break
        ctrl = bool(event.state & 0x0004)
        if clicked is None:
            if not ctrl: self._selected = set()
        elif ctrl:
            if clicked in self._selected: self._selected.discard(clicked)
            else:                          self._selected.add(clicked)
        else: self._selected = {clicked}
        self._redraw()

    def _redraw(self):
        c = self._canvas; c.delete("all"); self._hit_map = {}
        if not self._nodes:
            c.create_text(300, 100, text="Klicke auf '↺ Neu erstellen'",
                           font=("Segoe UI", 13), fill="#bbb")
            self._lbl_formula.config(text="—"); return
        W, H   = c.winfo_width() or 750, c.winfo_height() or 200
        GAP    = 28
        sizes  = [_measure(n) for n in self._nodes]
        total_w = sum(w for w, _ in sizes) + GAP * (len(self._nodes) - 1)
        x, mid_y = max(20, (W - total_w) // 2), H // 2
        for node in self._nodes:
            w, _ = _measure(node)
            _draw_node(c, node, x, mid_y, self._selected, self._hit_map, 0, node)
            x += w + GAP
        if len(self._nodes) == 1:
            self._lbl_formula.config(text=self._nodes[0].formula())
        else:
            self._lbl_formula.config(
                text="  ,  ".join(n.formula() for n in self._nodes) + "   ← verbinden!")

    # ── Solve ─────────────────────────────────────────────────────────────
    def _calculate(self):
        if len(self._nodes) != 1:
            messagebox.showwarning("Nicht fertig", "Alle Elemente müssen verbunden sein.")
            return
        root = self._nodes[0]
        sf   = self._sf()

        # Reset blue
        for row in self._table_rows.values():
            for sz in ['sz1', 'sz2']:
                for e in row[f'ents_{sz}'].values():
                    if e.cget("fg") == "blue":
                        e.delete(0, tk.END); e.config(fg="black", font=("Segoe UI", 10))
        for g in [self._gesamt_sz1, self._gesamt_sz2]:
            for e in g.values():
                if e.cget("fg") == "blue":
                    e.delete(0, tk.END); e.config(fg="black", font=("Segoe UI", 10))

        def _rv(e):
            raw = e.get().strip()
            return parse_value(raw) if raw else None

        def _build_tree_copy(sz):
            root_c = copy.deepcopy(root)
            leaves_c = root_c.all_r_nodes()
            # clear all vals
            def _clr(n):
                n.vals = {'U': None, 'I': None, 'R': None, 'P': None}
                for ch in n.children: _clr(ch)
            _clr(root_c)
            # set known values from entries
            for node, lc in zip(self._leaf_nodes, leaves_c):
                for k in ['U', 'I', 'R', 'P']:
                    lc.vals[k] = _rv(self._table_rows[node][f'ents_{sz}'][k])
            g = self._gesamt_sz1 if sz == 'sz1' else self._gesamt_sz2
            for k in ['U', 'I', 'R', 'P']:
                root_c.vals[k] = _rv(g[k])
            return root_c, leaves_c

        root1, leaves1 = _build_tree_copy('sz1')
        root2, leaves2 = _build_tree_copy('sz2')

        snap1 = _bk_snapshot(root1)
        snap2 = _bk_snapshot(root2)

        # Coupled R indices
        coupled_idx = {i for i, node in enumerate(self._leaf_nodes)
                       if node in self._table_rows and
                       self._table_rows[node]['coupled'].get()}

        # Solve: FPI outer loop
        _sz_dual_loop(root1, root2, leaves1, leaves2, coupled_idx,
                      self._ug_linked.get())

        # If unknowns remain: try bisection for 1 unknown coupled R
        _sz_bisect(root1, root2, leaves1, leaves2, coupled_idx,
                   self._ug_linked.get())

        # Konsistenzprüfung für beide Szenarien
        _leaves1 = root1.all_r_nodes() if len(self._nodes) == 1 else []
        _leaves2 = root2.all_r_nodes() if len(self._nodes) == 1 else []
        if _leaves1:
            _run_consistency_check(
                [n.vals.copy() for n in _leaves1],
                [n.label for n in _leaves1]
            )
        if _leaves2:
            _run_consistency_check(
                [n.vals.copy() for n in _leaves2],
                [f"{n.label}'" for n in _leaves2]
            )

        # Display results
        def _show(entry, val, sf):
            entry.delete(0, tk.END)
            entry.insert(0, f"{val:.{sf}g}")
            entry.config(fg="blue", font=("Segoe UI", 10, "bold"))

        def _was_unknown(node, sz, k):
            return _rv(self._table_rows[node][f'ents_{sz}'][k]) is None

        def _was_gest_unknown(sz, k):
            g = self._gesamt_sz1 if sz == 'sz1' else self._gesamt_sz2
            return _rv(g[k]) is None

        n_calc = 0
        for node, lc1, lc2 in zip(self._leaf_nodes, leaves1, leaves2):
            row = self._table_rows[node]
            for k in ['U', 'I', 'R', 'P']:
                if lc1.vals[k] is not None and _was_unknown(node, 'sz1', k):
                    _show(row['ents_sz1'][k], lc1.vals[k], sf); n_calc += 1
                if lc2.vals[k] is not None and _was_unknown(node, 'sz2', k):
                    _show(row['ents_sz2'][k], lc2.vals[k], sf); n_calc += 1

        for k in ['U', 'I', 'R', 'P']:
            if root1.vals[k] is not None and _was_gest_unknown('sz1', k):
                _show(self._gesamt_sz1[k], root1.vals[k], sf); n_calc += 1
            if root2.vals[k] is not None and _was_gest_unknown('sz2', k):
                _show(self._gesamt_sz2[k], root2.vals[k], sf); n_calc += 1

        r1 = root1.vals.get('R'); r2 = root2.vals.get('R')
        parts = []
        if r1: parts.append(f"Sz1: {r1:.{sf}g} Ω")
        if r2: parts.append(f"Sz2: {r2:.{sf}g} Ω")
        self._lbl_result.config(text="  |  ".join(parts) if parts else
                                     (f"✓ {n_calc} Wert(e)" if n_calc else "—"))

    def _clear_table(self):
        for row in self._table_rows.values():
            for sz in ['sz1', 'sz2']:
                for e in row[f'ents_{sz}'].values():
                    e.delete(0, tk.END); e.config(fg="black", font=("Segoe UI", 10))
        for g in [self._gesamt_sz1, self._gesamt_sz2]:
            for e in g.values():
                e.delete(0, tk.END); e.config(fg="black", font=("Segoe UI", 10))
        if self._lbl_result: self._lbl_result.config(text="")




# ==========================================
# BATTERIE / INNENWIDERSTAND FRAME
# ==========================================

class BatterieFrame(tk.Frame):
    def __init__(self, parent, app_ref=None):
        super().__init__(parent, bg="#f0f4f8")
        self._app_ref    = app_ref
        self._bat_entries = {}
        self._build_ui()

    def _sf(self):
        return self._app_ref.sig_figs_var.get() if self._app_ref else 4

    def _build_ui(self):
        scroll_canvas = tk.Canvas(self, bg="#f0f4f8", highlightthickness=0)
        scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb = tk.Scrollbar(self, orient=tk.VERTICAL, command=scroll_canvas.yview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_canvas.configure(yscrollcommand=vsb.set)
        inner = tk.Frame(scroll_canvas, bg="#f0f4f8", padx=40, pady=20)
        inner_win = scroll_canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda e: scroll_canvas.configure(
                       scrollregion=scroll_canvas.bbox("all")))
        scroll_canvas.bind("<Configure>",
                            lambda e: scroll_canvas.itemconfig(inner_win, width=e.width))

        box = tk.LabelFrame(
            inner,
            text=" Batterie / Innenwiderstand"
                 "  —  alle Felder sind Ein- und Ausgabe  (blau = berechnet) ",
            padx=12, pady=8, bg="white", font=("Segoe UI", 10, "bold"))
        box.pack(fill=tk.X)
        box.columnconfigure(1, weight=1)

        def _sec(text, row, color):
            tk.Label(box, text=text, bg=color, fg="#334155",
                     font=("Segoe UI", 9, "bold"), anchor="w", padx=6, pady=3
                     ).grid(row=row, column=0, columnspan=3, sticky="ew",
                            padx=0, pady=(8, 2))

        def _row(label, key, unit, row):
            tk.Label(box, text=label, bg="white", anchor="w",
                     font=("Segoe UI", 10), width=30
                     ).grid(row=row, column=0, sticky="w", padx=(6, 0), pady=3)
            e = tk.Entry(box, width=14, justify="right", font=("Segoe UI", 10),
                         relief=tk.FLAT)
            e.config(highlightbackground="#cbd5e1", highlightthickness=1)
            e.grid(row=row, column=1, sticky="ew", padx=6, pady=3)
            tk.Label(box, text=unit, bg="white", fg="#64748b",
                     font=("Segoe UI", 10), width=9, anchor="w"
                     ).grid(row=row, column=2, sticky="w")
            e.bind("<Return>",   lambda ev: self._berechnen())
            e.bind("<KeyPress>", lambda ev, ent=e: ent.config(fg="black", font=("Segoe UI", 10)))
            self._bat_entries[key] = e

        _sec("  Quelle", 0, "#eff6ff")
        _row("Leerlaufspannung  (EMK)",   "E",     "V",  1)
        _row("Innenwiderstand",            "Ri",    "Ω",  2)
        _row("Kurzschlussstrom",           "Isc",   "A",  3)

        _sec("  Last", 4, "#fff7ed")
        _row("Außenwiderstand",            "Ra",    "Ω",  5)
        _row("Klemmspannung",              "Uk",    "V",  6)
        _row("Strom",                      "I",     "A",  7)

        _sec("  Leistung", 8, "#f0fdf4")
        _row("Nutzleistung  (an Last)",    "Pa",    "W",  9)
        _row("Verlustleistung  (an Ri)",   "Pi",    "W", 10)
        _row("Gesamtleistung",             "P_ges", "W", 11)

        _BATTERIE_TIPS = {
            'E':     "Quellenspannung / EMK der Batterie [V]",
            'Ri':    "Innenwiderstand der Quelle [Ω]",
            'Isc':   "Kurzschlussstrom: Isc = E / Ri [A]",
            'Ra':    "Lastwiderstand (Außenwiderstand) [Ω]",
            'Uk':    "Klemmspannung: Uk = E − Ri·I [V]",
            'I':     "Stromfluss: I = E / (Ri + Ra) [A]",
            'Pa':    "Nutzleistung an der Last: Pa = Uk·I [W]",
            'Pi':    "Verlustleistung im Innenwiderstand: Pi = Ri·I² [W]",
            'P_ges': "Gesamtleistung der Quelle: P_ges = E·I = Pa + Pi [W]",
        }
        for key, tip in _BATTERIE_TIPS.items():
            if key in self._bat_entries:
                _Tooltip(self._bat_entries[key], tip)

        btn_f = tk.Frame(inner, bg="#f0f4f8", pady=10)
        btn_f.pack(fill=tk.X)
        tk.Button(btn_f, text="  BERECHNEN  ", command=self._berechnen,
                  bg="#059669", fg="white", font=("Segoe UI", 12, "bold"),
                  width=15, pady=5).pack(side=tk.LEFT)
        tk.Button(btn_f, text="Leeren", command=self._leeren,
                  bg="#dc2626", fg="white", font=("Segoe UI", 10),
                  padx=10, pady=5).pack(side=tk.LEFT, padx=12)
        self._lbl_status = tk.Label(btn_f, text="",
                                     font=("Segoe UI", 10), bg="#f0f4f8", fg="#065f46")
        self._lbl_status.pack(side=tk.LEFT)

    def _berechnen(self):
        for e in self._bat_entries.values():
            if e.cget("fg") == "blue":
                e.delete(0, tk.END)
                e.config(fg="black", font=("Segoe UI", 10))

        def _rf(key):
            raw = self._bat_entries[key].get().strip()
            if not raw: return None
            try:    return float(raw.replace(',', '.'))
            except: return None

        v    = {k: _rf(k) for k in self._bat_entries}
        snap = dict(v)

        for k, val in v.items():
            if val is not None and val < 0:
                self._lbl_status.config(
                    text=f"Fehler: {k} darf nicht negativ sein.", fg="#dc2626")
                return

        solve_batterie(v)
        _run_consistency_check([v], ["Batterie"])

        sf     = self._sf()
        n_calc = 0
        for k, val in v.items():
            if val is not None and snap[k] is None:
                e = self._bat_entries[k]
                e.delete(0, tk.END)
                e.insert(0, f"{val:.{sf}g}")
                e.config(fg="blue", font=("Segoe UI", 10, "bold"))
                n_calc += 1

        if n_calc > 0:
            self._lbl_status.config(text=f"✓  {n_calc} Wert(e) berechnet", fg="#059669")
        elif any(v[k] is not None for k in v):
            self._lbl_status.config(
                text="Nicht genug Eingaben für eine Berechnung.", fg="#c2410c")
        else:
            self._lbl_status.config(
                text="Bitte mindestens 2 Felder ausfüllen.", fg="#64748b")

    def _leeren(self):
        for e in self._bat_entries.values():
            e.delete(0, tk.END)
            e.config(fg="black", font=("Segoe UI", 10))
        self._lbl_status.config(text="", fg="#065f46")


# ==========================================
# HAUPT-APP
# ==========================================

class ElektrotechnikSolverApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Elektrotechnik Rechner v12.1")
        self.root.geometry("1080x700")
        self.root.minsize(820, 560)
        self.sig_figs_var = tk.IntVar(value=4)
        self._current_mode = 0
        self.create_widgets()
        self.switch_mode(0)
        self.root.bind("<F5>", self._f5_handler)

    def _f5_handler(self, event=None):
        m = self._current_mode
        if   m == 0: self.baukasten_container._calculate()
        elif m == 1: self.solve_costs()
        elif m == 4: self.szenarien_container._calculate()
        elif m == 5: self.batterie_container._berechnen()

    def _dec_sf(self):
        v = self.sig_figs_var.get()
        if v > 1: self.sig_figs_var.set(v - 1)

    def _inc_sf(self):
        v = self.sig_figs_var.get()
        if v < 8: self.sig_figs_var.set(v + 1)

    def create_widgets(self):
        top_bar = tk.Frame(self.root, bg="#1a2332")
        top_bar.pack(fill=tk.X)

        # Left: app name
        tk.Label(top_bar, text="ET Rechner", fg="#64748b", bg="#1a2332",
                 font=("Segoe UI", 10, "bold"), padx=16, pady=10).pack(side=tk.LEFT)

        # Center: tab buttons
        tabs_frame = tk.Frame(top_bar, bg="#1a2332")
        tabs_frame.pack(side=tk.LEFT, fill=tk.Y)
        _tab_labels = ["Baukasten", "Energiekosten", "Farbcode", "Präfix", "Szenarien", "Batterie"]
        self._mode_idx = tk.IntVar(value=0)
        self._tab_btns = []
        for i, lbl in enumerate(_tab_labels):
            btn = tk.Button(tabs_frame, text=lbl, bg="#1a2332", fg="#8fa0b8",
                            font=("Segoe UI", 10), bd=0, padx=14, pady=10,
                            relief=tk.FLAT, cursor="hand2",
                            activebackground="#243448", activeforeground="#ffffff",
                            command=lambda idx=i: self.switch_mode(idx))
            btn.pack(side=tk.LEFT)
            self._tab_btns.append(btn)

        _tab_tips = [
            "Visueller Schaltungseditor: Widerstände kombinieren und U/I/R/P berechnen",
            "Bidirektionaler Stromkostenrechner mit Tag-/Nacht-Tarif (Schweizer Rappen)",
            "Widerstandsfarbcode (IEC 60062) — Farbe ↔ Wert in beide Richtungen",
            "SI-Einheitenpräfixe umrechnen: Tera, Giga, Mega, kilo, milli, mikro …",
            "Zwei Szenarien vergleichen — gleiche Schaltung, verschiedene Werte",
            "Batterie/Innenwiderstand: E, Ri, Ra, Uk, I, Pa, Pi bidirektional berechnen",
        ]
        for btn, tip in zip(self._tab_btns, _tab_tips):
            _Tooltip(btn, tip)

        # Right: significant figures
        sf_frame = tk.Frame(top_bar, bg="#1a2332")
        sf_frame.pack(side=tk.RIGHT, padx=12)
        tk.Label(sf_frame, text="Stellen:", fg="#64748b", bg="#1a2332",
                 font=("Segoe UI", 9), pady=10).pack(side=tk.LEFT)
        tk.Button(sf_frame, text="−", command=self._dec_sf, bg="#243448", fg="#cbd5e1",
                  font=("Segoe UI", 10, "bold"), padx=6, pady=6, bd=0, relief=tk.FLAT,
                  cursor="hand2", activebackground="#334155").pack(side=tk.LEFT, padx=(4, 0))
        tk.Label(sf_frame, textvariable=self.sig_figs_var, bg="#1a2332", fg="#f1f5f9",
                 font=("Consolas", 11, "bold"), width=2).pack(side=tk.LEFT)
        tk.Button(sf_frame, text="+", command=self._inc_sf, bg="#243448", fg="#cbd5e1",
                  font=("Segoe UI", 10, "bold"), padx=6, pady=6, bd=0, relief=tk.FLAT,
                  cursor="hand2", activebackground="#334155").pack(side=tk.LEFT, padx=(0, 4))
        _Tooltip(sf_frame, "Anzahl signifikanter Stellen in den Ergebnisfeldern (1–8)")

        # --- Baukasten ---
        self.baukasten_container = BaukastenFrame(self.root, app_ref=self)

        # --- Energiekosten (bidirektional) ---
        self.cost_container = tk.Frame(self.root, bg="#f0f4f8")
        self.cost_entries = {}

        scroll_canvas = tk.Canvas(self.cost_container, bg="#f0f4f8", highlightthickness=0)
        scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb_cost = tk.Scrollbar(self.cost_container, orient=tk.VERTICAL,
                                 command=scroll_canvas.yview)
        vsb_cost.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_canvas.configure(yscrollcommand=vsb_cost.set)
        inner = tk.Frame(scroll_canvas, bg="#f0f4f8", padx=40, pady=20)
        inner_win = scroll_canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda e: scroll_canvas.configure(
                       scrollregion=scroll_canvas.bbox("all")))
        scroll_canvas.bind("<Configure>",
                            lambda e: scroll_canvas.itemconfig(inner_win, width=e.width))

        cost_box = tk.LabelFrame(
            inner,
            text=" Kosten-Parameter  —  alle Felder sind Ein- und Ausgabe (blau = berechnet) ",
            padx=12, pady=8, bg="white", font=("Segoe UI", 10, "bold"))
        cost_box.pack(fill=tk.X)
        cost_box.columnconfigure(1, weight=1)

        def _sec(text, row, color):
            tk.Label(cost_box, text=text, bg=color, fg="#334155",
                     font=("Segoe UI", 9, "bold"), anchor="w", padx=6, pady=3
                     ).grid(row=row, column=0, columnspan=3, sticky="ew",
                            padx=0, pady=(8, 2))

        def _row(label, key, default, unit, row):
            tk.Label(cost_box, text=label, bg="white", anchor="w",
                     font=("Segoe UI", 10), width=24
                     ).grid(row=row, column=0, sticky="w", padx=(6, 0), pady=3)
            e = tk.Entry(cost_box, width=14, justify="right", font=("Segoe UI", 10),
                         relief=tk.FLAT)
            e.config(highlightbackground="#cbd5e1", highlightthickness=1)
            e.grid(row=row, column=1, sticky="ew", padx=6, pady=3)
            if default:
                e.insert(0, default)
            tk.Label(cost_box, text=unit, bg="white", fg="#64748b",
                     font=("Segoe UI", 10), width=9, anchor="w"
                     ).grid(row=row, column=2, sticky="w")
            e.bind("<Return>",   lambda ev: self.solve_costs())
            e.bind("<KeyPress>", lambda ev, ent=e: ent.config(fg="black",
                                                               font=("Segoe UI", 10)))
            self.cost_entries[key] = e

        _sec("  Gerät", 0, "#eff6ff")
        _row("Leistung",          "P",          "100",  "W",       1)

        _sec("  Tagbetrieb", 2, "#fff7ed")
        _row("Stunden/Tag",       "h_tag",      "8",    "h/Tag",   3)
        _row("Tagstarif",         "pr_tag",     "28.0", "Rp/kWh",  4)
        _row("Kosten Tag",        "cost_tag",   "",     "CHF",     5)

        _sec("  Nachtbetrieb", 6, "#fdf2f8")
        _row("Stunden/Nacht",     "h_nacht",    "16",   "h/Nacht", 7)
        _row("Nachttarif",        "pr_nacht",   "18.0", "Rp/kWh",  8)
        _row("Kosten Nacht",      "cost_nacht", "",     "CHF",     9)

        _sec("  Laufzeit & Gesamt", 10, "#f0fdf4")
        _row("Anzahl Tage",       "tage",       "30",   "Tage",   11)
        _row("Verbrauch gesamt",  "kwh_gesamt", "",     "kWh",    12)
        _row("Kosten gesamt",     "cost_total", "",     "CHF",    13)

        btn_f = tk.Frame(inner, bg="#f0f4f8", pady=10)
        btn_f.pack(fill=tk.X)
        tk.Button(btn_f, text="  BERECHNEN (F5)  ", command=self.solve_costs,
                  bg="#1d4ed8", fg="white", font=("Segoe UI", 12, "bold"),
                  pady=6).pack(side=tk.LEFT)
        tk.Button(btn_f, text="Leeren", command=self._clear_cost_table,
                  bg="#dc2626", fg="white", font=("Segoe UI", 10),
                  padx=10, pady=6).pack(side=tk.LEFT, padx=12)
        self.lbl_cost_status = tk.Label(btn_f, text="",
                                         font=("Segoe UI", 10), bg="#f0f4f8", fg="#065f46")
        self.lbl_cost_status.pack(side=tk.LEFT)

        # --- Farbcode ---
        self.farbcode_container = FarbcodeFrame(self.root, app_ref=self)

        # --- Präfix-Umrechner ---
        self.prefix_container = PraefixFrame(self.root, app_ref=self)

        # --- Szenarien-Vergleich ---
        self.szenarien_container = SzenarienVisuelFrame(self.root, app_ref=self)

        # --- Batterie / Innenwiderstand ---
        self.batterie_container = BatterieFrame(self.root, app_ref=self)


    def switch_mode(self, m=0):
        self._current_mode = m
        for i, btn in enumerate(self._tab_btns):
            if i == m:
                btn.config(bg="#243448", fg="#ffffff")
            else:
                btn.config(bg="#1a2332", fg="#8fa0b8")
        containers = [
            self.baukasten_container,
            self.cost_container,
            self.farbcode_container,
            self.prefix_container,
            self.szenarien_container,
            self.batterie_container,
        ]
        for c in containers:
            c.pack_forget()
        containers[m].pack(fill=tk.BOTH, expand=True)

    def solve_costs(self):
        # Blau-Felder zurücksetzen
        for e in self.cost_entries.values():
            if e.cget("fg") == "blue":
                e.delete(0, tk.END)
                e.config(fg="black", font=("Segoe UI", 10))

        # Eingaben lesen
        def _rf(key):
            raw = self.cost_entries[key].get().strip()
            if not raw: return None
            try:    return float(raw.replace(',', '.'))
            except: return None

        v = {k: _rf(k) for k in self.cost_entries}
        snap = dict(v)

        # Validierung der Roheingaben
        LABELS = {
            'P': 'Leistung', 'h_tag': 'Stunden Tag', 'h_nacht': 'Stunden Nacht',
            'pr_tag': 'Tagstarif', 'pr_nacht': 'Nachttarif', 'tage': 'Anzahl Tage',
            'cost_tag': 'Kosten Tag', 'cost_nacht': 'Kosten Nacht',
            'cost_total': 'Kosten Gesamt', 'kwh_gesamt': 'Verbrauch',
        }
        for k, val in v.items():
            if val is not None and val < 0:
                self.lbl_cost_status.config(
                    text=f"Fehler: {LABELS.get(k, k)} darf nicht negativ sein.",
                    fg="#dc2626")
                return

        if v['h_tag'] is not None and v['h_nacht'] is not None:
            if v['h_tag'] + v['h_nacht'] > 24:
                self.lbl_cost_status.config(
                    text=f"Fehler: {v['h_tag']}h + {v['h_nacht']}h = "
                         f"{v['h_tag'] + v['h_nacht']}h > 24h/Tag",
                    fg="#dc2626")
                return

        # Bidirektional lösen
        solve_costs_bidirectional(v)

        # Ergebnis auf > 24h prüfen
        h_t = v.get('h_tag') or 0
        h_n = v.get('h_nacht') or 0
        if h_t + h_n > 24:
            messagebox.showwarning(
                "Plausibilitätshinweis",
                f"Ergebnis: Stunden Tag ({h_t:.3g}h) + Nacht ({h_n:.3g}h) "
                f"= {h_t + h_n:.3g}h > 24h/Tag\nBitte Eingaben prüfen.")

        # Ergebnisse anzeigen (berechnete Felder blau)
        def _fmt(key, val):
            if key in ('cost_tag', 'cost_nacht', 'cost_total'): return f"{val:.2f}"
            if key == 'kwh_gesamt':                              return f"{val:.3f}"
            if key in ('h_tag', 'h_nacht'):
                return str(int(round(val))) if abs(val - round(val)) < 1e-6 else f"{val:.3f}"
            if key == 'tage':
                return str(int(round(val))) if abs(val - round(val)) < 0.05 else f"{val:.2f}"
            return f"{val:.4g}"

        n_calc = 0
        for k, val in v.items():
            if val is not None and snap[k] is None:
                s = _fmt(k, val)
                e = self.cost_entries[k]
                e.delete(0, tk.END)
                e.insert(0, s)
                e.config(fg="blue", font=("Segoe UI", 10, "bold"))
                n_calc += 1

        if n_calc > 0:
            self.lbl_cost_status.config(text=f"✓  {n_calc} Wert(e) berechnet", fg="#059669")
        elif any(v[k] is not None for k in v):
            self.lbl_cost_status.config(
                text="Nicht genug Eingaben für eine Berechnung.", fg="#c2410c")
        else:
            self.lbl_cost_status.config(text="Bitte mindestens 4 Felder ausfüllen.", fg="#64748b")

    def _clear_cost_table(self):
        for e in self.cost_entries.values():
            e.delete(0, tk.END)
            e.config(fg="black", font=("Segoe UI", 10))
        self.lbl_cost_status.config(text="", fg="#065f46")


if __name__ == "__main__":
    root = tk.Tk()
    app  = ElektrotechnikSolverApp(root)
    root.mainloop()
