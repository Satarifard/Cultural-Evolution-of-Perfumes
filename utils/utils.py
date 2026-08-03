"""
Shared utility functions for the Cultural Evolution of Perfumes project.

Sections:
  1. Parsing helpers (perfumers, notes, accords, ratings, patent descriptors)
  2. Entropy & divergence (Shannon entropy, KL, JSD)
  3. Network helpers (build collaboration graph, count structures, pair exclusion)
  4. Accord/note ranking & labeling
  5. Rating helpers
  6. Growth-model functions (double logistic, Richards)
"""

import ast
import json
import re
from math import log2
from collections import defaultdict
from itertools import combinations

import numpy as np
import pandas as pd

# ═══════════════════════════════════════════════════════════════════════════════
# 1.  PARSING HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def parse_perfumer(cell):
    """Parse the 'perfumer' column into a list of individual perfumer names."""
    if pd.isna(cell):
        return []
    try:
        s = str(cell).strip()
        if s.startswith('[') and s.endswith(']'):
            parsed = ast.literal_eval(s)
            if isinstance(parsed, list):
                return [str(name).strip() for name in parsed if str(name).strip()]
            cleaned = str(parsed).strip()
            return [cleaned] if cleaned else []
        return [p.strip() for p in s.split(",") if p.strip()]
    except Exception:
        return [name.strip() for name in str(cell).split(',') if name.strip()]


_PERFUMER_PRODUCT_RE = re.compile(r'eau de|parfum|cologne|toilette|\bedt\b|\bedp\b|\d', re.I)


def clean_perfumer_artifacts(perfumers, house=None):
    """Drop non-person tokens that scraping leaked into the 'perfumer' field.

    Two artifact types are removed:
      1. House+product concatenations -- the perfume's own *house* name is a prefix of
         the token, glued (no space) to a new capitalized word (a product), e.g. house
         "Perfumer's Workshop" -> token "Perfumer's WorkshopTea Rose". Real eponymous
         perfumers (token == house) and names that merely start with the house
         ("Yosh Han"/house "Yosh"; "Frederic Munoz"/house "Frederic M") are KEPT, because
         their boundary is a space or a lowercase mid-word character rather than a new
         capitalized word.
      2. Product / lab / code labels -- tokens containing 'eau de', 'parfum', 'cologne',
         'edt'/'edp', 'toilette', or a digit (e.g. 'URBIS PARFUMS', 'FAV 105').

    Apostrophes are treated as spaces so the token matches house values that store
    "Perfumer s Workshop" without the apostrophe. *perfumers* is the list returned by
    parse_perfumer; *house* is the row's house string (NaN/None tolerated). Order kept.
    """
    hn = re.sub(r"[’']", " ", house.strip()).lower() if isinstance(house, str) else None
    out = []
    for p in perfumers:
        pn = re.sub(r"[’']", " ", p).lower()
        if hn and len(hn) >= 4 and len(pn) > len(hn) and pn.startswith(hn) and p[len(hn)].isupper():
            continue                       # house name glued to a product
        if _PERFUMER_PRODUCT_RE.search(p):
            continue                       # product / lab / code label, not a person
        out.append(p)
    return out


def parse_notes(notes_str):
    """
    Parse the 'notes' column and return a list of note names.

    The column stores a JSON list of single-key dicts, e.g.
        [{"Saffron": {"vote": 11}}, {"Rose": {"vote": 8}}]
    Returns: ["Saffron", "Rose", ...]
    """
    if pd.isna(notes_str):
        return []
    try:
        notes_str = str(notes_str).replace('""', '"')
        return [key for item in ast.literal_eval(notes_str) for key in item.keys()]
    except Exception:
        return []


def parse_notes_weighted(notes_str):
    """
    Parse 'notes' column into a dict {note_name: fraction} using 'vote'.

    Only notes with weight > 0 are included; fractions sum to 1.
    """
    if pd.isna(notes_str):
        return {}
    try:
        notes_str = str(notes_str).replace('""', '"')
        notes_list = ast.literal_eval(notes_str)
        total = sum(
            data.get('vote', 0)
            for item in notes_list
            for data in item.values()
            if data.get('vote', 0) > 0
        )
        if total <= 0:
            return {}
        return {
            note: data['vote'] / total
            for item in notes_list
            for note, data in item.items()
            if data.get('vote', 0) > 0
        }
    except (ValueError, SyntaxError):
        return {}


def parse_notes_tenet(notes_str):
    """
    Parse 'notes' column into a dict {note_name: weight_tenet}.

    Used for innovation (JSD) calculations.
    """
    if pd.isna(notes_str):
        return {}
    try:
        notes_str = str(notes_str).replace('""', '"')
        notes_list = ast.literal_eval(notes_str)
        return {
            note: data.get('weight_tenet', 0)
            for item in notes_list
            for note, data in item.items()
        }
    except (ValueError, SyntaxError):
        return {}


def parse_accords(accords_str):
    """
    Parse the 'accords' column and return a list of accord names (value > 0).

    The column stores a JSON dict, e.g. {"woody": 100.0, "amber": 92.0, ...}
    """
    if pd.isna(accords_str):
        return []
    try:
        return [k for k, v in ast.literal_eval(str(accords_str)).items() if v > 0]
    except Exception:
        return []


def parse_accords_dict(accords_str):
    """
    Parse the 'accords' column and return the full dict {accord: frequency}.
    """
    if pd.isna(accords_str):
        return {}
    try:
        return ast.literal_eval(str(accords_str))
    except (ValueError, SyntaxError):
        return {}


def parse_average_rating(rating_str):
    """
    Parse a rating dict string (e.g. '{"1": 2, "2": 3, ...}') and return
    the weighted average rating.
    """
    if pd.isna(rating_str):
        return 0.0
    try:
        rating_str = str(rating_str).replace('""', '"')
        rating_dict = ast.literal_eval(rating_str)
        total_votes = sum(float(v) for v in rating_dict.values())
        weighted_sum = sum(float(k) * float(v) for k, v in rating_dict.items())
        return weighted_sum / total_votes if total_votes > 0 else 0.0
    except Exception:
        return 0.0


def extract_patent_terms(cell):
    """
    Split patent descriptor fields on comma/semicolon.

    Use ONLY for patent descriptor columns (Primary descriptor, Descriptor 2, etc.),
    NOT for perfume notes (which are JSON and need parse_notes()).
    """
    if pd.isna(cell):
        return []
    return [t.strip() for seg in str(cell).split(';')
            for t in seg.split(',') if t.strip()]


# ═══════════════════════════════════════════════════════════════════════════════
# 2.  ENTROPY & DIVERGENCE
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_shannon_entropy(weight_dict):
    """Shannon entropy H = -sum(p_i * log2(p_i)) in bits.

    Values are normalized internally to sum to 1, so the result is a valid
    entropy whether the input holds raw weights/counts or already-normalized
    fractions. Returns 0.0 for an empty dict or non-positive total mass.
    """
    total = sum(weight_dict.values())
    if total <= 0:
        return 0.0
    return -sum((v / total) * log2(v / total) for v in weight_dict.values() if v > 0)


def to_probability_dist(weight_dict):
    """Normalise a {name: weight} dict so values sum to 1."""
    total = sum(weight_dict.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in weight_dict.items()}


def build_historical_distribution(rows, key='parsed_notes'):
    """
    Aggregate per-perfume note/accord weights into one probability distribution.

    *rows* is a list of dicts/Series each containing a dict at ``key``.
    """
    combined = defaultdict(float)
    for row in rows:
        for note, wt in row[key].items():
            combined[note] += wt
    return to_probability_dist(combined)


def kl_divergence(p_dist, q_dist, epsilon=1e-9):
    """KL(P || Q) = sum(p_i * log2(p_i / q_i))."""
    return sum(
        p_i * log2(p_i / max(q_dist.get(note, 0.0), epsilon))
        for note, p_i in p_dist.items() if p_i > 0
    )


def js_divergence(p_dist, q_dist):
    """
    Jensen-Shannon divergence (base 2, bounded [0, 1]).

    JSD(P || Q) = 0.5 * KL(P || M) + 0.5 * KL(Q || M), where M = (P+Q)/2.
    """
    all_keys = set(p_dist) | set(q_dist)
    M = {k: 0.5 * (p_dist.get(k, 0.0) + q_dist.get(k, 0.0)) for k in all_keys}
    return 0.5 * kl_divergence(p_dist, M) + 0.5 * kl_divergence(q_dist, M)


# ═══════════════════════════════════════════════════════════════════════════════
# 3.  NETWORK HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def build_network_nx(df, perfumer_col='filtered_perfumers'):
    """
    Build an undirected NetworkX collaboration graph and return
    the largest connected component.
    """
    import networkx as nx

    edge_weights = {}
    for perfumers in df[perfumer_col]:
        if len(perfumers) < 2:
            continue
        for pair in combinations(perfumers, 2):
            pair = tuple(sorted(pair))
            edge_weights[pair] = edge_weights.get(pair, 0) + 1

    G = nx.Graph()
    for (u, v), w in edge_weights.items():
        G.add_edge(u, v, weight=w)

    if G.number_of_nodes() == 0:
        return G
    largest_cc = max(nx.connected_components(G), key=len)
    return G.subgraph(largest_cc).copy()


def build_count_structures(df, perfumer_labels_df, label_col):
    """
    Build count structures for pair-specific exclusion at distance 1.

    Returns
    -------
    total_counts : dict  {perfumer: {label: count}}
    partner_counts : dict  {p: {q: {label: count}}}

    Parameters
    ----------
    df : DataFrame with 'parsed_perfumers' and a parsed label list column.
    perfumer_labels_df : DataFrame with columns ['perfumer', label_col, 'count'].
    label_col : str, either 'accord' or 'note'.
    """
    total_counts = {}
    for _, row in perfumer_labels_df.iterrows():
        p = row['perfumer']
        lab = row[label_col]
        total_counts.setdefault(p, {})
        total_counts[p][lab] = total_counts[p].get(lab, 0) + 1

    # Determine which column in df holds the parsed labels list
    parsed_col = 'parsed_accords' if label_col == 'accord' else 'parsed_top_notes'

    partner_counts = {}
    for _, row in df.iterrows():
        perfumers = row['parsed_perfumers']
        labels = row.get(parsed_col, [])
        if not perfumers or not labels:
            continue
        # For accords stored as dicts, extract keys
        if isinstance(labels, dict):
            labels = list(labels.keys())
        for p in perfumers:
            partner_counts.setdefault(p, {})
            for q in perfumers:
                if p == q:
                    continue
                partner_counts[p].setdefault(q, {})
                for lab in labels:
                    partner_counts[p][q][lab] = partner_counts[p][q].get(lab, 0) + 1

    return total_counts, partner_counts


def subtract_counts(counts_a, counts_b):
    """Element-wise subtraction of two label-count dicts; floor at zero."""
    if not counts_a:
        return {}
    counts_b = counts_b or {}
    out = {}
    for k, v in counts_a.items():
        val = v - counts_b.get(k, 0)
        if val > 0:
            out[k] = val
    return out


def rank_from_counts(counts_dict, rank_index):
    """
    From a {label: count} dict, normalise and return the label at a given
    1-based rank.  Returns None if unavailable.
    """
    if not counts_dict:
        return None
    total = sum(counts_dict.values())
    if total <= 0:
        return None
    items = sorted(
        ((lab, cnt / total) for lab, cnt in counts_dict.items()),
        key=lambda x: (-x[1], x[0])
    )
    if 1 <= rank_index <= len(items):
        return items[rank_index - 1][0]
    return None


def compute_observed_with_pair_exclusion(
    G, total_counts, partner_counts, global_rank_labels,
    max_distance=6, n_ranks=5
):
    """
    Compute observed P(same label) at each network distance for ranks 1..n_ranks.

    At distance == 1 each node's rank-r label is recomputed EXCLUDING joint works
    with the specific partner.  For d >= 2 global labels are used.
    """
    import networkx as nx

    if G.number_of_nodes() == 0:
        empty = {r: {d: 0.0 for d in range(1, max_distance + 1)} for r in range(1, n_ranks + 1)}
        return empty, {d: 0 for d in range(1, max_distance + 1)}

    distances = dict(nx.all_pairs_shortest_path_length(G))
    totals = {d: 0 for d in range(1, max_distance + 1)}
    matches = {r: {d: 0 for d in range(1, max_distance + 1)} for r in range(1, n_ranks + 1)}

    for u in distances:
        for v, dist in distances[u].items():
            if u == v or not (1 <= dist <= max_distance):
                continue
            totals[dist] += 1
            for r in range(1, n_ranks + 1):
                if dist == 1:
                    u_ex = subtract_counts(total_counts.get(u), partner_counts.get(u, {}).get(v))
                    v_ex = subtract_counts(total_counts.get(v), partner_counts.get(v, {}).get(u))
                    u_label = rank_from_counts(u_ex, r)
                    v_label = rank_from_counts(v_ex, r)
                else:
                    u_labels = global_rank_labels.get(u, [])
                    v_labels = global_rank_labels.get(v, [])
                    u_label = u_labels[r - 1] if len(u_labels) >= r else None
                    v_label = v_labels[r - 1] if len(v_labels) >= r else None

                if u_label is not None and v_label is not None and u_label == v_label:
                    matches[r][dist] += 1

    observed = {
        r: {d: (matches[r][d] / totals[d]) if totals[d] > 0 else 0.0
            for d in range(1, max_distance + 1)}
        for r in range(1, n_ranks + 1)
    }
    return observed, totals


def compute_probability_by_distance(G, label_map, max_distance=6):
    """
    Given a {node: label} map, compute P(same label) at each network distance.
    """
    import networkx as nx

    if G.number_of_nodes() == 0:
        return {d: 0.0 for d in range(1, max_distance + 1)}

    distances = dict(nx.all_pairs_shortest_path_length(G))
    match_counts = {d: 0 for d in range(1, max_distance + 1)}
    total_counts = {d: 0 for d in range(1, max_distance + 1)}

    for u in distances:
        for v, dist in distances[u].items():
            if u == v or not (1 <= dist <= max_distance):
                continue
            total_counts[dist] += 1
            a, b = label_map.get(u), label_map.get(v)
            if a is not None and b is not None and a == b:
                match_counts[dist] += 1

    return {
        d: (match_counts[d] / total_counts[d]) if total_counts[d] > 0 else 0.0
        for d in range(1, max_distance + 1)
    }


def simulate_random_networks(G, label_map, num_simulations=10000, max_distance=6):
    """
    Shuffle node labels and compute null P(same label) statistics.

    Returns (mean_dict, std_dict) over *num_simulations* shuffles.
    """
    if G.number_of_nodes() == 0:
        zero = {d: 0.0 for d in range(1, max_distance + 1)}
        return zero, zero

    nodes = list(G.nodes())
    labels = [label_map.get(n) for n in nodes]

    sims = []
    for _ in range(num_simulations):
        np.random.shuffle(labels)
        shuffled = dict(zip(nodes, labels))
        sims.append(compute_probability_by_distance(G, shuffled, max_distance))

    mean = {d: np.mean([s[d] for s in sims]) for d in range(1, max_distance + 1)}
    std = {d: np.std([s[d] for s in sims], ddof=1) for d in range(1, max_distance + 1)}
    return mean, std


# ═══════════════════════════════════════════════════════════════════════════════
# 4.  ACCORD / NOTE RANKING & LABELING
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_top_n_labels(perfumer_labels_df, label_col, n=5):
    """
    Given rows of {perfumer, label_col, count}, compute normalised counts,
    keep top-n per perfumer, and assign rank 1..n.

    Returns a DataFrame with columns [perfumer, label_col, normalized_count, rank].
    """
    agg = (
        perfumer_labels_df
        .groupby(['perfumer', label_col], as_index=False)['count']
        .sum()
    )
    totals = agg.groupby('perfumer')['count'].transform('sum')
    agg['normalized_count'] = agg['count'] / totals
    agg = agg.sort_values(['perfumer', 'normalized_count'], ascending=[True, False])
    top_df = agg.groupby('perfumer').head(n).copy()
    top_df['rank'] = (
        top_df.groupby('perfumer')['normalized_count']
        .rank(method='first', ascending=False)
        .astype(int)
    )
    return top_df[top_df['rank'] <= n]


def build_global_rank_labels(top_df, label_col, n_ranks=5):
    """
    Build {perfumer: [rank1_label, rank2_label, ...]} from a top-n DataFrame.
    """
    labels = {}
    for p, grp in top_df.sort_values(['perfumer', 'rank']).groupby('perfumer'):
        lab_list = [None] * n_ranks
        for _, r in grp.iterrows():
            lab_list[r['rank'] - 1] = r[label_col]
        while lab_list and lab_list[-1] is None:
            lab_list.pop()
        labels[p] = lab_list
    return labels


def calculate_dominant_accord(perfumer_accords_df, top_accords=None):
    """
    Aggregate accord frequencies per perfumer and return the dominant accord.

    If *top_accords* is given, accords not in the list are mapped to 'other'.
    Returns a DataFrame with [perfumer, dominant_accord, frequency].
    """
    agg = (
        perfumer_accords_df
        .groupby(['perfumer', 'accord'])['frequency']
        .mean()
        .reset_index()
        .sort_values(['perfumer', 'frequency'], ascending=[True, False])
    )
    dominant = (
        agg.groupby('perfumer')
        .first()
        .reset_index()
        .rename(columns={'accord': 'dominant_accord'})
    )
    if top_accords is not None:
        dominant['dominant_accord'] = dominant['dominant_accord'].apply(
            lambda x: x if x in top_accords else 'other'
        )
    return dominant


# ═══════════════════════════════════════════════════════════════════════════════
# 5.  RATING HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_weighted_average(df, column, max_scale=5):
    """
    Parse each cell in *df[column]* as a dict of {rating_value: count},
    compute a weighted average rating, and store in df[f'average_{column}'].
    """
    df[column] = df[column].apply(
        lambda x: x if isinstance(x, dict)
        else json.loads(x) if pd.notna(x) else {}
    )

    def _get_weighted_avg(d):
        if not d or sum(d.values()) == 0:
            return np.nan
        numeric_keys = sorted(int(k) for k in d.keys())
        actual_max = numeric_keys[-1]
        scale_factor = max_scale / actual_max
        total_weighted = sum((int(k) * scale_factor) * v for k, v in d.items())
        total_counts = sum(d.values())
        return total_weighted / total_counts

    df[f'average_{column}'] = df[column].apply(_get_weighted_avg)


def parse_rating_dict(rating_str, scale=5):
    """
    Weighted-average rating from a vote-count dict string, e.g. '{"1": 2, "2": 3, ...}'.

    Only star keys in [1, scale] are counted (use scale=4 for sillage, 5 otherwise);
    no rescaling is applied, so the result stays on the native 1..scale axis.
    Returns np.nan if parsing fails or there are no votes.
    """
    if pd.isna(rating_str):
        return np.nan
    try:
        rating_dict = ast.literal_eval(str(rating_str).replace('""', '"'))
        if not isinstance(rating_dict, dict):
            return np.nan
        total_votes = 0.0
        weighted_sum = 0.0
        for star_str, count in rating_dict.items():
            star = int(star_str)
            if 1 <= star <= scale:
                total_votes += count
                weighted_sum += star * count
        return weighted_sum / total_votes if total_votes > 0 else np.nan
    except (ValueError, SyntaxError):
        return np.nan


# ═══════════════════════════════════════════════════════════════════════════════
# 6.  GROWTH-MODEL FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def double_logistic(t, A, K1, r1, t1, K2, r2, t2):
    """
    Double logistic with free lower limit A:
      f(t) = A + K1/(1+exp(-r1*(t-t1))) + K2/(1+exp(-r2*(t-t2)))
    """
    term1 = K1 / (1.0 + np.exp(-r1 * (t - t1)))
    term2 = K2 / (1.0 + np.exp(-r2 * (t - t2)))
    return A + term1 + term2


def richards(t, A, K, r, t0, nu):
    """
    Richards (generalised logistic) model:
      N(t) = A + (K - A) / [1 + exp(-r*(t-t0))]^nu
    """
    return A + (K - A) / (1.0 + np.exp(-r * (t - t0))) ** nu


# ═══════════════════════════════════════════════════════════════════════════════
# 7.  DISRUPTION (CD) INDEX
# ═══════════════════════════════════════════════════════════════════════════════

def compute_cd_indices(df, windows=(3, 5, 10), id_col='id', year_col='year',
                       reminds_col='this_perfume_reminds_ids'):
    """Funk & Owen-Smith consolidation-disruption (CD) index at one or more year
    windows, computed on the 'this perfume reminds of ...' network as a citation
    analog (edge F -> B means perfume F references / builds on B).

    For a focal perfume F (year t) and window w, among the perfumes that reference F
    within (t, t+w]:  type i (disruptive) do NOT also reference F's references;
    type j (consolidating) do.  Type k = perfumes that reference F's references but
    not F (same window).  CD_w = (n_i - n_j) / (n_i + n_j + n_k) in [-1, +1].

    Returns a DataFrame with *id_col* and one ``cd{w}`` column per window (NaN where
    F has no forward citers in the window or no year).
    """
    def _parse_reminds(s):
        if pd.isna(s):
            return []
        try:
            x = ast.literal_eval(str(s))
            return [int(i) for i in x] if isinstance(x, list) else []
        except Exception:
            return []

    rem = df[reminds_col].apply(_parse_reminds)
    valid = set(int(i) for i in df[id_col])
    yr = {int(i): y for i, y in zip(df[id_col], pd.to_numeric(df[year_col], errors='coerce')) if pd.notna(y)}

    refs = {}
    citers = defaultdict(set)
    for F, r in zip(df[id_col], rem):
        F = int(F)
        rs = {b for b in r if b in valid and b != F}
        refs[F] = rs
        for j in rs:
            citers[j].add(F)

    ids = [int(i) for i in df[id_col]]
    out = {w: [] for w in windows}
    for F in ids:
        t = yr.get(F)
        if t is None:
            for w in windows:
                out[w].append(np.nan)
            continue
        rset = refs.get(F, set())
        cf = citers.get(F, set())
        fwd = [(yr[g], bool(refs.get(g, set()) & rset))
               for g in citers.get(F, ()) if yr.get(g) is not None and yr[g] > t]
        cite_refs = set()
        for r in rset:
            cite_refs |= citers.get(r, set())
        nk_years = [yr[h] for h in cite_refs
                    if h != F and h not in cf and yr.get(h) is not None and yr[h] > t]
        for w in windows:
            lim = t + w
            ni = sum(1 for yg, cons in fwd if yg <= lim and not cons)
            nj = sum(1 for yg, cons in fwd if yg <= lim and cons)
            if ni + nj == 0:
                out[w].append(np.nan)
                continue
            nk = sum(1 for yh in nk_years if yh <= lim)
            out[w].append((ni - nj) / (ni + nj + nk))

    res = pd.DataFrame({id_col: ids})
    for w in windows:
        res[f'cd{w}'] = out[w]
    return res
