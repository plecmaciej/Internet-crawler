import networkx as nx
import numpy as np
from collections import Counter

G = nx.read_edgelist("graph.txt", create_using=nx.DiGraph())

in_degree = dict(G.in_degree())
out_degree = dict(G.out_degree())

in_values = list(in_degree.values())
out_values = list(out_degree.values())

N = G.number_of_nodes()

def build_P_k(values, N):
    counts = Counter(values)
    k_values = sorted(counts.keys())
    k_values = [k for k in k_values if k > 0]
    P_values = [counts[k] / N for k in k_values]
    return np.array(k_values, dtype=float), np.array(P_values, dtype=float)

k_in, P_in = build_P_k(in_values, N)
k_out, P_out = build_P_k(out_values, N)

log_k_in = np.log(k_in)
log_P_in = np.log(P_in)

log_k_out = np.log(k_out)
log_P_out = np.log(P_out)

def ols_fit(log_k, log_P):
    n = len(log_k)
    sum_x = np.sum(log_k)
    sum_y = np.sum(log_P)
    sum_xy = np.sum(log_k * log_P)
    sum_x2 = np.sum(log_k ** 2)

    #Σᵢ (log_Pᵢ − (a·log_kᵢ + b))²
    #x = log_k, y = log_P
    #a = [n·Σ(x·y) − Σx·Σy] / [n·Σ(x²) − (Σx)²]
    #b = (Σy − a·Σx) / n

    a = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
    b = (sum_y - a * sum_x) / n
    return a, b

a_in, b_in = ols_fit(log_k_in, log_P_in)
a_out, b_out = ols_fit(log_k_out, log_P_out)

gamma_in = -a_in
gamma_out = -a_out

print("gamma_in (OLS) =", gamma_in)
print("gamma_out (OLS) =", gamma_out)

a_in_check, b_in_check = np.polyfit(log_k_in, log_P_in, 1)
a_out_check, b_out_check = np.polyfit(log_k_out, log_P_out, 1)

gamma_in_check = -a_in_check
gamma_out_check = -a_out_check

print("gamma_in_check (OLS) =", gamma_in_check)
print("gamma_out_check (OLS) =", gamma_out_check)

def r_squared(log_k, log_P, a, b):
    y_pred = a * log_k + b
    y_mean = np.mean(log_P)
    ss_res = np.sum((log_P - y_pred) ** 2)
    ss_tot = np.sum((log_P - y_mean) ** 2)
    return 1 - ss_res / ss_tot

r_in = r_squared(log_k_in, log_P_in, a_in, b_in)
r_out = r_squared(log_k_out, log_P_out, a_out, b_out)

print("r squared in =", r_in)
print("r squared out =", r_out)


k_min = 1

# Maximum Likelihood Estimator for discrete power-law exponent (Clauset-Shalizi-Newman)
# gamma_hat = 1 + n * [ sum_i ln(k_i / (k_min - 0.5)) ]^-1
def compute_mle_gamma(raw_values, k_min=1):

    filtered_k = [k for k in raw_values if k >= k_min]
    n = len(filtered_k)

    if n == 0:
        return None, 0, filtered_k

    S = sum(np.log(k / (k_min - 0.5)) for k in filtered_k)
    gamma = 1 + n / S

    return gamma, n, filtered_k

gamma_in_mle, n_in, filtered_in = compute_mle_gamma(in_values, k_min)
gamma_out_mle, n_out, filtered_out = compute_mle_gamma(out_values, k_min)

print("\n--- RESULTS SUMMARY ---")
print(f"OLS:  gamma_in = {gamma_in:.4f} | gamma_out = {gamma_out:.4f}")
print(f"MLE:  gamma_in = {gamma_in_mle:.4f} | gamma_out = {gamma_out_mle:.4f} (sample n_in={n_in}, n_out={n_out})")


# Kolmogorov-Smirnov goodness-of-fit test
# Compares the empirical CDF S(k) of the data against the theoretical CDF P(k)
# of the fitted discrete power-law distribution P(k) ~ k^(-gamma)
# D = max_k | S(k) - P(k) |
# D close to 0 -> good fit; larger D -> the data deviates more from a power law
def calculate_ks_stat(filtered_k, k_min, gamma):
    filtered_k = np.array(filtered_k)
    n = len(filtered_k)
    k_max = np.max(filtered_k)

    k_range = np.arange(k_min, k_max + 1)

    # theoretical PMF: P(k) proportional to k^(-gamma), normalized over the observed range
    pmf_theory = k_range.astype(float) ** (-gamma)
    pmf_theory /= np.sum(pmf_theory)
    cdf_theory = np.cumsum(pmf_theory)

    # empirical PMF: fraction of nodes with each degree value
    counts = Counter(filtered_k)
    pmf_empirical = np.array([counts.get(k, 0) for k in k_range], dtype=float) / n
    cdf_empirical = np.cumsum(pmf_empirical)

    # KS statistic: largest vertical distance between the two CDFs
    D = np.max(np.abs(cdf_empirical - cdf_theory))
    return D

D_in = calculate_ks_stat(filtered_in, k_min, gamma_in_mle)
D_out = calculate_ks_stat(filtered_out, k_min, gamma_out_mle)

print("\n--- KOLMOGOROV-SMIRNOV TEST ---")
print(f"D_in  = {D_in:.4f}")
print(f"D_out = {D_out:.4f}")
print("(D close to 0 indicates a good fit to the power-law model; higher D indicates deviation)")