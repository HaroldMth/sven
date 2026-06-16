/*
 * Sven — Seven OS Package Manager
 * HANS TECH © 2024 — GPL v3
 * libsven/graph.c — Topological sort (DFS) for install ordering
 *
 * Replaces the pure-Python DFS in resolver/sorter.py.
 * Works on a flat integer representation of the graph so ctypes
 * can pass it without marshalling Python dicts.
 *
 * Python side builds:
 *   - names[]    : array of n package name strings
 *   - adj[]      : flat adjacency list (see below)
 *   - adj_idx[]  : adj_idx[i] = start offset of node i's edges in adj[]
 *   - adj_cnt[]  : adj_cnt[i] = number of edges for node i
 *
 * sven_topo_sort() writes the topologically-sorted node indices into
 * out_order[] and returns the number of nodes written.
 * Detected cycles are broken and reported via cycles_out[].
 */

#include <string.h>
#include <stdlib.h>

#define VISIT_NONE  0
#define VISIT_TEMP  1   /* currently on DFS stack (cycle detection) */
#define VISIT_DONE  2


/* ── Internal DFS ────────────────────────────────────────────── */

static void dfs(
    int node,
    const int  *adj,        /* flat adjacency list */
    const int  *adj_idx,    /* adj_idx[i] = start in adj[] */
    const int  *adj_cnt,    /* adj_cnt[i] = # edges */
    char       *state,      /* VISIT_NONE/TEMP/DONE per node */
    int        *order,      /* output (written in reverse) */
    int        *order_pos,  /* current write position */
    int        *cycles,     /* indices of nodes involved in a cycle */
    int        *cycle_pos   /* current cycle write position */
) {
    if (state[node] == VISIT_TEMP) {
        /* Cycle detected — record node if not already there */
        for (int i = 0; i < *cycle_pos; i++) {
            if (cycles[i] == node) return;
        }
        cycles[(*cycle_pos)++] = node;
        return;
    }
    if (state[node] == VISIT_DONE) return;

    state[node] = VISIT_TEMP;

    int start = adj_idx[node];
    int count = adj_cnt[node];
    for (int e = 0; e < count; e++) {
        int dep = adj[start + e];
        dfs(dep, adj, adj_idx, adj_cnt, state,
            order, order_pos, cycles, cycle_pos);
    }

    state[node] = VISIT_DONE;
    order[(*order_pos)++] = node;
}


/* ── sven_topo_sort ──────────────────────────────────────────────────────────
 *
 * Topologically sort `n_nodes` nodes given a flat adjacency list.
 *
 * Parameters:
 *   n_nodes    — total number of nodes
 *   adj        — flat edge array:  adj[adj_idx[i] .. adj_idx[i]+adj_cnt[i]-1]
 *                contains the dependency indices of node i
 *   adj_idx    — start offset into adj[] for each node
 *   adj_cnt    — number of edges per node
 *   node_order — array of node indices sorted from deepest dep to top level
 *                (caller allocates, size n_nodes)
 *   cycles_out — indices of nodes that participate in a cycle
 *                (caller allocates, size n_nodes)
 *   n_cycles   — receives the count of cycle nodes written
 *
 * Returns number of nodes written to node_order.
 * Nodes are written leaves-first so iterating node_order gives install order.
 */
int sven_topo_sort(
    int        n_nodes,
    const int *adj,
    const int *adj_idx,
    const int *adj_cnt,
    int       *node_order,
    int       *cycles_out,
    int       *n_cycles
) {
    if (n_nodes <= 0 || !node_order) return 0;

    char *state = (char *)calloc(n_nodes, sizeof(char));
    if (!state) return -1;

    int *tmp_order = (int *)malloc(n_nodes * sizeof(int));
    if (!tmp_order) { free(state); return -1; }

    int order_pos = 0;
    int cycle_pos = 0;

    /* Visit all nodes (sorted by index for deterministic output) */
    for (int i = 0; i < n_nodes; i++) {
        if (state[i] == VISIT_NONE) {
            dfs(i, adj, adj_idx, adj_cnt, state,
                tmp_order, &order_pos, cycles_out ? cycles_out : tmp_order,
                &cycle_pos);
        }
    }

    /* DFS post-order already gives install order (leaves first) — copy directly */
    for (int i = 0; i < order_pos; i++) {
        node_order[i] = tmp_order[i];
    }

    if (n_cycles) *n_cycles = cycle_pos;

    free(state);
    free(tmp_order);
    return order_pos;
}
