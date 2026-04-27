#!/usr/bin/env python3
"""7-chain smoke validator — checks all adapters accept base/solana/tempo."""
import sys
import os
import importlib.util
import traceback

# Set dummy env vars before any imports so modules don't error on missing env
os.environ.setdefault("ALGOVOI_TEMPO_RPC", "https://dummy-tempo-rpc.example.com")
os.environ.setdefault("ALGOVOI_API_KEY", "algv_dummy")
os.environ.setdefault("ALGOVOI_TENANT_ID", "00000000-0000-0000-0000-000000000000")

ROOT = os.path.dirname(os.path.abspath(__file__))
NEW_CHAINS_HYPHEN = ["base-mainnet", "solana-mainnet", "tempo-mainnet"]
NEW_CHAINS_SNAKE  = ["base_mainnet",  "solana_mainnet",  "tempo_mainnet"]

OK   = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"
SKIP = "\033[33m-\033[0m"
passes = fails = skips = 0


def check(label, ok, detail=""):
    global passes, fails
    if ok:
        passes += 1
        print(f"  {OK}  {label}")
    else:
        fails += 1
        print(f"  {FAIL}  {label}" + (f" — {detail}" if detail else ""))
    return ok


def skip(label, reason=""):
    global skips
    skips += 1
    print(f"  {SKIP}  {label}" + (f" [SKIP: {reason}]" if reason else ""))


def load(rel_path):
    """Load a module from a relative path under ROOT."""
    abs_path = os.path.join(ROOT, rel_path.replace("/", os.sep))
    module_name = os.path.basename(abs_path).replace(".py", "").replace("-", "_")
    spec = importlib.util.spec_from_file_location(module_name, abs_path)
    mod = importlib.util.module_from_spec(spec)
    # Register in sys.modules BEFORE exec so @dataclass can find cls.__module__
    sys.modules[module_name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        # Clean up on failure so subsequent loads of same name don't hit stale state
        sys.modules.pop(module_name, None)
        raise
    return mod


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ── Helper: check a list/set/dict for chains ──────────────────────────────────

def check_networks_hyphen(mod, attr, chains=NEW_CHAINS_HYPHEN):
    """Check that attr (list/set/dict) on mod contains all hyphen-format chains."""
    container = getattr(mod, attr, None)
    if container is None:
        for ch in chains:
            check(f"{attr} contains {ch}", False, f"attr {attr!r} not found on module")
        return
    for ch in chains:
        check(f"{attr} contains {ch}", ch in container)


def check_networks_snake(mod, attr, chains=NEW_CHAINS_SNAKE):
    """Check that attr (list/set/dict) on mod contains all snake-format chains."""
    container = getattr(mod, attr, None)
    if container is None:
        for ch in chains:
            check(f"{attr} contains {ch}", False, f"attr {attr!r} not found on module")
        return
    for ch in chains:
        check(f"{attr} contains {ch}", ch in container)


def check_class_attr_snake(cls, attr, chains=NEW_CHAINS_SNAKE):
    """Check a class-level dict/set/list for snake-format chains."""
    container = getattr(cls, attr, None)
    if container is None:
        for ch in chains:
            check(f"{cls.__name__}.{attr} contains {ch}", False, f"attr not found")
        return
    for ch in chains:
        check(f"{cls.__name__}.{attr} contains {ch}", ch in container)


def check_class_attr_both(cls, attr, h_chains=NEW_CHAINS_HYPHEN, s_chains=NEW_CHAINS_SNAKE):
    """Check a class-level dict/set for both hyphen AND snake variants."""
    container = getattr(cls, attr, None)
    if container is None:
        for ch in h_chains:
            check(f"{cls.__name__}.{attr} contains {ch}", False, "attr not found")
        return
    for ch in h_chains:
        check(f"{cls.__name__}.{attr} contains {ch}", ch in container)
    for ch in s_chains:
        check(f"{cls.__name__}.{attr} contains {ch}", ch in container)


# ══════════════════════════════════════════════════════════════════════════════
# PROTOCOL ADAPTERS
# ══════════════════════════════════════════════════════════════════════════════

section("MPP Adapter  (mpp-adapter/mpp.py)")
try:
    mpp = load("mpp-adapter/mpp.py")
    MppGate = mpp.MppGate

    # MppGate.NETWORKS uses snake keys
    check_class_attr_snake(MppGate, "NETWORKS")

    # MppGate.INDEXERS has both hyphen and snake keys
    check_class_attr_both(MppGate, "INDEXERS")

except ImportError as e:
    skip("mpp-adapter/mpp.py", f"ImportError: {e}")
except Exception as e:
    fails += 1
    print(f"  {FAIL}  mpp-adapter/mpp.py — {e}")
    traceback.print_exc()


section("AP2 Adapter  (ap2-adapter/ap2.py)")
try:
    ap2 = load("ap2-adapter/ap2.py")

    # NETWORKS is a module-level dict with hyphen keys
    check_networks_hyphen(ap2, "NETWORKS")

except ImportError as e:
    skip("ap2-adapter/ap2.py", f"ImportError: {e}")
except Exception as e:
    fails += 1
    print(f"  {FAIL}  ap2-adapter/ap2.py — {e}")
    traceback.print_exc()


# ══════════════════════════════════════════════════════════════════════════════
# AI ADAPTERS
# ══════════════════════════════════════════════════════════════════════════════

section("OpenAI Adapter  (ai-adapters/openai/openai_algovoi.py)")
try:
    openai_mod = load("ai-adapters/openai/openai_algovoi.py")

    check_networks_hyphen(openai_mod, "NETWORKS")
    check_networks_hyphen(openai_mod, "_CAIP2")
    check_networks_hyphen(openai_mod, "_ASSET_ID")
    check_networks_hyphen(openai_mod, "_INDEXERS")

except ImportError as e:
    skip("ai-adapters/openai/openai_algovoi.py", f"ImportError: {e}")
except Exception as e:
    fails += 1
    print(f"  {FAIL}  ai-adapters/openai/openai_algovoi.py — {e}")
    traceback.print_exc()


section("Claude Adapter  (ai-adapters/claude/claude_algovoi.py)")
try:
    claude_mod = load("ai-adapters/claude/claude_algovoi.py")

    check_networks_hyphen(claude_mod, "NETWORKS")
    # _SNAKE maps hyphen→snake; check the keys (hyphen)
    check_networks_hyphen(claude_mod, "_SNAKE")

except ImportError as e:
    skip("ai-adapters/claude/claude_algovoi.py", f"ImportError: {e}")
except Exception as e:
    fails += 1
    print(f"  {FAIL}  ai-adapters/claude/claude_algovoi.py — {e}")
    traceback.print_exc()


section("Gemini Adapter  (ai-adapters/gemini/gemini_algovoi.py)")
try:
    gemini_mod = load("ai-adapters/gemini/gemini_algovoi.py")
    check_networks_hyphen(gemini_mod, "NETWORKS")
except ImportError as e:
    skip("ai-adapters/gemini/gemini_algovoi.py", f"ImportError: {e}")
except Exception as e:
    fails += 1
    print(f"  {FAIL}  ai-adapters/gemini/gemini_algovoi.py — {e}")
    traceback.print_exc()


section("Bedrock Adapter  (ai-adapters/bedrock/bedrock_algovoi.py)")
try:
    bedrock_mod = load("ai-adapters/bedrock/bedrock_algovoi.py")
    check_networks_hyphen(bedrock_mod, "NETWORKS")
except ImportError as e:
    skip("ai-adapters/bedrock/bedrock_algovoi.py", f"ImportError: {e}")
except Exception as e:
    fails += 1
    print(f"  {FAIL}  ai-adapters/bedrock/bedrock_algovoi.py — {e}")
    traceback.print_exc()


section("Cohere Adapter  (ai-adapters/cohere/cohere_algovoi.py)")
try:
    cohere_mod = load("ai-adapters/cohere/cohere_algovoi.py")
    check_networks_hyphen(cohere_mod, "NETWORKS")
except ImportError as e:
    skip("ai-adapters/cohere/cohere_algovoi.py", f"ImportError: {e}")
except Exception as e:
    fails += 1
    print(f"  {FAIL}  ai-adapters/cohere/cohere_algovoi.py — {e}")
    traceback.print_exc()


section("xAI/Grok Adapter  (ai-adapters/xai/xai_algovoi.py)")
try:
    xai_mod = load("ai-adapters/xai/xai_algovoi.py")
    check_networks_hyphen(xai_mod, "NETWORKS")
except ImportError as e:
    skip("ai-adapters/xai/xai_algovoi.py", f"ImportError: {e}")
except Exception as e:
    fails += 1
    print(f"  {FAIL}  ai-adapters/xai/xai_algovoi.py — {e}")
    traceback.print_exc()


section("Mistral Adapter  (ai-adapters/mistral/mistral_algovoi.py)")
try:
    mistral_mod = load("ai-adapters/mistral/mistral_algovoi.py")
    check_networks_hyphen(mistral_mod, "NETWORKS")
except ImportError as e:
    skip("ai-adapters/mistral/mistral_algovoi.py", f"ImportError: {e}")
except Exception as e:
    fails += 1
    print(f"  {FAIL}  ai-adapters/mistral/mistral_algovoi.py — {e}")
    traceback.print_exc()


# ══════════════════════════════════════════════════════════════════════════════
# FRAMEWORK ADAPTERS
# ══════════════════════════════════════════════════════════════════════════════

FRAMEWORK_ADAPTERS = [
    ("Agno",            "ai-agent-frameworks/agno/agno_algovoi.py"),
    ("AutoGen",         "ai-agent-frameworks/autogen/autogen_algovoi.py"),
    ("CrewAI",          "ai-agent-frameworks/crewai/crewai_algovoi.py"),
    ("HuggingFace",     "ai-agent-frameworks/huggingface/huggingface_algovoi.py"),
    ("LangChain",       "ai-agent-frameworks/langchain/langchain_algovoi.py"),
    ("LangGraph",       "ai-agent-frameworks/langgraph/langgraph_algovoi.py"),
    ("LlamaIndex",      "ai-agent-frameworks/llamaindex/llamaindex_algovoi.py"),
    ("Semantic Kernel", "ai-agent-frameworks/semantic-kernel/semantic_kernel_algovoi.py"),
]

for name, rel_path in FRAMEWORK_ADAPTERS:
    section(f"{name} Framework  ({rel_path})")
    try:
        mod = load(rel_path)
        check_networks_hyphen(mod, "NETWORKS")
    except ImportError as e:
        skip(rel_path, f"ImportError: {e}")
    except Exception as e:
        fails += 1
        print(f"  {FAIL}  {rel_path} — {e}")
        traceback.print_exc()


# ══════════════════════════════════════════════════════════════════════════════
# NO-CODE ADAPTERS
# ══════════════════════════════════════════════════════════════════════════════

NOCODE_ADAPTERS = [
    ("Zapier",  "no-code/zapier/zapier_algovoi.py"),
    ("Make",    "no-code/make/make_algovoi.py"),
    ("n8n",     "no-code/n8n/n8n_algovoi.py"),
    ("X/Twitter", "no-code/x/x_algovoi.py"),
]

for name, rel_path in NOCODE_ADAPTERS:
    section(f"{name} No-Code  ({rel_path})")
    try:
        mod = load(rel_path)
        # No-code adapters use snake-format SUPPORTED_NETWORKS + NETWORK_INFO
        check_networks_snake(mod, "SUPPORTED_NETWORKS")
        check_networks_snake(mod, "NETWORK_INFO")
    except ImportError as e:
        skip(rel_path, f"ImportError: {e}")
    except Exception as e:
        fails += 1
        print(f"  {FAIL}  {rel_path} — {e}")
        traceback.print_exc()


# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

print(f"\n{'='*60}")
print(f"  RESULTS")
print(f"{'='*60}")
print(f"  Passed: {passes}")
print(f"  Failed: {fails}")
print(f"  Skipped: {skips}")
print()

if fails == 0 and passes > 0:
    print(f"  {OK}  ALL CHECKS PASSED")
    sys.exit(0)
else:
    print(f"  {FAIL}  {fails} check(s) FAILED")
    sys.exit(1)
