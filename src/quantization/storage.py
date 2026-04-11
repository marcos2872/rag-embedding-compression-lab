"""
src/quantization/storage.py
-----------------------------
Bit-packing e serialização/deserialização de embeddings quantizados.

Bit-packing obrigatório para taxas de compressão corretas:
  2-bit: 4 índices por byte  → dim=384 → 96  bytes/vetor (16× vs float32)
  4-bit: 2 índices por byte  → dim=384 → 192 bytes/vetor  (8× vs float32)
  8-bit: 1 índice por byte   → dim=384 → 384 bytes/vetor  (4× vs float32)

Sem packing, 2-bit e 4-bit usariam 384 bytes/vetor = apenas 4× compressão.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np


# ── Bit packing ────────────────────────────────────────────────────────────────

def pack_indices(indices_2d: np.ndarray, bits: int) -> np.ndarray:
    """
    Empacota índices inteiros com `bits` bits por índice.

    indices_2d : [N, D] int array, valores 0 .. 2^bits-1
    Retorna    : [N, ceil(D*bits/8)] uint8
    """
    N, D = indices_2d.shape
    # Expande cada índice em `bits` bits (big-endian) — vetorizado
    powers = np.int32(1) << np.arange(bits - 1, -1, -1, dtype=np.int32)   # [bits]
    bit_array = ((indices_2d[:, :, np.newaxis] & powers) > 0).astype(np.uint8)
    flat = bit_array.reshape(N, D * bits)                                   # [N, D*bits]
    # Padding até múltiplo de 8
    remainder = (D * bits) % 8
    if remainder:
        flat = np.pad(flat, ((0, 0), (0, 8 - remainder)))
    return np.packbits(flat, axis=1)                                        # [N, ceil(D*bits/8)]


def unpack_indices(packed: np.ndarray, bits: int, D: int) -> np.ndarray:
    """
    Desempacota índices de `bits` bits.

    packed  : [N, ceil(D*bits/8)] uint8
    Retorna : [N, D] int32
    """
    N = packed.shape[0]
    unpacked = np.unpackbits(packed, axis=1)[:, : D * bits]   # [N, D*bits]
    bit_array = unpacked.reshape(N, D, bits)                    # [N, D, bits]
    powers = (2 ** np.arange(bits - 1, -1, -1)).astype(np.int32)
    return (bit_array.astype(np.int32) * powers).sum(axis=2)   # [N, D]


def pack_signs(signs_2d: np.ndarray) -> np.ndarray:
    """
    Empacota signs {+1, -1} como bits individuais.

    signs_2d : [N, D] float32/int, valores +1 ou -1
    Retorna  : [N, ceil(D/8)] uint8  →  1 bit por sinal (não 1 byte)
    """
    N, D = signs_2d.shape
    binary = ((signs_2d + 1) // 2).astype(np.uint8)    # +1→1, -1→0
    remainder = D % 8
    if remainder:
        binary = np.pad(binary, ((0, 0), (0, 8 - remainder)))
    return np.packbits(binary, axis=1)                  # [N, ceil(D/8)]


def unpack_signs(packed: np.ndarray, D: int) -> np.ndarray:
    """
    packed  : [N, ceil(D/8)] uint8
    Retorna : [N, D] float32, valores +1.0 ou -1.0
    """
    bits = np.unpackbits(packed, axis=1)[:, :D]        # [N, D]
    return (bits.astype(np.float32) * 2.0) - 1.0


# ── Uniform ────────────────────────────────────────────────────────────────────

def save_uniform(
    indices: np.ndarray,   # [N, D] int32
    norms: np.ndarray,     # [N] float32
    state,                 # UniformState
    path: str | Path,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        str(path),
        indices_packed = pack_indices(indices, state.bits),
        norms          = norms.astype(np.float16),
        q_min          = np.float32(state.q_min),
        q_scale        = np.float32(state.q_scale),
        bits           = np.int32(state.bits),
        dim            = np.int32(state.dim),
        variant        = np.array("uniform"),
    )


def load_uniform(path: str | Path):
    """Retorna (indices [N,D], norms [N], UniformState)."""
    from src.quantization.scalar_uniform import UniformState
    data = np.load(str(path), allow_pickle=True)
    bits = int(data["bits"])
    dim  = int(data["dim"])
    state = UniformState(
        q_min  = float(data["q_min"]),
        q_scale= float(data["q_scale"]),
        bits   = bits,
        dim    = dim,
    )
    indices = unpack_indices(data["indices_packed"], bits, dim)
    norms   = data["norms"].astype(np.float32)
    return indices, norms, state


# ── Lloyd-Max ──────────────────────────────────────────────────────────────────

def save_lloyd(
    indices: np.ndarray,
    norms: np.ndarray,
    codebook: np.ndarray,
    bits: int,
    dim: int,
    path: str | Path,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        str(path),
        indices_packed = pack_indices(indices, bits),
        norms          = norms.astype(np.float16),
        codebook       = codebook.astype(np.float32),
        bits           = np.int32(bits),
        dim            = np.int32(dim),
        variant        = np.array("lloyd_max"),
    )


def load_lloyd(path: str | Path):
    """Retorna (indices [N,D], norms [N], codebook [K])."""
    data     = np.load(str(path), allow_pickle=True)
    bits     = int(data["bits"])
    dim      = int(data["dim"])
    indices  = unpack_indices(data["indices_packed"], bits, dim)
    norms    = data["norms"].astype(np.float32)
    codebook = data["codebook"].astype(np.float32)
    return indices, norms, codebook


# ── TurboQuantMSE ──────────────────────────────────────────────────────────────

def save_turbo_mse(
    indices: np.ndarray,
    norms: np.ndarray,
    state,   # TurboMSEState
    path: str | Path,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        str(path),
        indices_packed = pack_indices(indices, state.bits),
        norms          = norms.astype(np.float16),
        codebook       = state.codebook.astype(np.float32),
        R              = state.R.astype(np.float32),
        bits           = np.int32(state.bits),
        dim            = np.int32(state.dim),
        seed           = np.int32(state.seed),
        variant        = np.array("turbo_mse"),
    )


def load_turbo_mse(path: str | Path):
    """Retorna (indices [N,D], norms [N], TurboMSEState)."""
    from src.quantization.turboquant_mse import TurboMSEState
    data  = np.load(str(path), allow_pickle=True)
    bits  = int(data["bits"])
    dim   = int(data["dim"])
    state = TurboMSEState(
        R        = data["R"].astype(np.float32),
        codebook = data["codebook"].astype(np.float32),
        dim      = dim,
        bits     = bits,
        seed     = int(data["seed"]),
    )
    indices = unpack_indices(data["indices_packed"], bits, dim)
    norms   = data["norms"].astype(np.float32)
    return indices, norms, state


# ── TurboQuantProd ─────────────────────────────────────────────────────────────

def save_turbo_prod(
    mse_indices: np.ndarray | None,
    mse_norms: np.ndarray,
    signs: np.ndarray,
    gammas: np.ndarray,
    state,   # TurboProdState
    path: str | Path,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    save_dict: dict = dict(
        mse_norms        = mse_norms.astype(np.float16),
        qjl_gammas       = gammas.astype(np.float16),
        qjl_signs_packed = pack_signs(signs),
        R                = state.R.astype(np.float32),
        S                = state.S.astype(np.float32),
        bits             = np.int32(state.bits),
        mse_bits         = np.int32(state.mse_bits),
        dim              = np.int32(state.dim),
        seed             = np.int32(state.seed),
        qjl_seed         = np.int32(state.qjl_seed),
        variant          = np.array("turbo_prod"),
    )
    if mse_indices is not None and state.mse_bits > 0:
        save_dict["mse_indices_packed"] = pack_indices(mse_indices, state.mse_bits)
        save_dict["codebook"]           = state.codebook.astype(np.float32)
    np.savez_compressed(str(path), **save_dict)


def load_turbo_prod(path: str | Path):
    """Retorna (mse_indices|None, mse_norms, signs, gammas, TurboProdState)."""
    from src.quantization.turboquant_prod import TurboProdState
    data     = np.load(str(path), allow_pickle=True)
    bits     = int(data["bits"])
    mse_bits = int(data["mse_bits"])
    dim      = int(data["dim"])
    state = TurboProdState(
        R        = data["R"].astype(np.float32),
        S        = data["S"].astype(np.float32),
        codebook = data["codebook"].astype(np.float32) if "codebook" in data else np.array([], dtype=np.float32),
        dim      = dim,
        bits     = bits,
        mse_bits = mse_bits,
        seed     = int(data["seed"]),
        qjl_seed = int(data["qjl_seed"]),
    )
    mse_indices = None
    if mse_bits > 0 and "mse_indices_packed" in data:
        mse_indices = unpack_indices(data["mse_indices_packed"], mse_bits, dim)
    mse_norms = data["mse_norms"].astype(np.float32)
    signs     = unpack_signs(data["qjl_signs_packed"], dim)
    gammas    = data["qjl_gammas"].astype(np.float32)
    return mse_indices, mse_norms, signs, gammas, state
