"""Eval scorer for audio provider ABC contract enforcement.

Deterministic eval (no API calls, no cost) that verifies:
- All concrete providers are importable
- Each concrete provider is a subclass of its ABC
- Each concrete provider implements all abstract methods
- Method signatures match the ABC (correct parameter names/types)
- Instantiating an incomplete subclass raises TypeError

Cost: $0 (no API calls)

Usage:
    python -m src.evals.score_provider_contract setup
    python -m src.evals.score_provider_contract score
    python -m src.evals.score_provider_contract cleanup
"""
import inspect
import sys

from src.evals.eval_harness import EvalHarness


# Provider pairs: (ABC module path, ABC class name, concrete module path, concrete class name)
PROVIDER_PAIRS: list[tuple[str, str, str, str]] = [
    (
        "src.tts.tts_provider",
        "TTSProvider",
        "src.tts.elevenlabs_provider",
        "ElevenLabsProvider",
    ),
    (
        "src.tts.sound_effect_provider",
        "SoundEffectProvider",
        "src.tts.elevenlabs_sound_effect_provider",
        "ElevenLabsSoundEffectProvider",
    ),
    (
        "src.tts.ambient_provider",
        "AmbientProvider",
        "src.tts.elevenlabs_ambient_provider",
        "ElevenLabsAmbientProvider",
    ),
]

# ABCs that have no concrete implementation yet (only check importability)
ABC_ONLY: list[tuple[str, str]] = [
    ("src.tts.music_provider", "MusicProvider"),
]


def _import_class(module_path: str, class_name: str) -> type:
    """Import and return a class from a module path."""
    import importlib
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)  # type: ignore[no-any-return]


def _get_abstract_methods(abc_cls: type) -> set[str]:
    """Return the set of abstract method names on an ABC."""
    abstract: set[str] = set()
    for name in dir(abc_cls):
        obj = getattr(abc_cls, name, None)
        if getattr(obj, "__isabstractmethod__", False):
            abstract.add(name)
    return abstract


def _signature_params(cls: type, method_name: str) -> list[str]:
    """Return parameter names (excluding 'self') for a method on a class."""
    method = getattr(cls, method_name)
    sig = inspect.signature(method)
    return [
        name for name, param in sig.parameters.items()
        if name != "self"
    ]


class ScoreProviderContract(EvalHarness):
    """Deterministic eval for audio provider ABC contracts."""

    def setup(self) -> None:
        """No setup needed for deterministic contract checks."""
        print("No setup needed (deterministic eval, no API calls).")
        print("\nRun: python -m src.evals.score_provider_contract score")

    def score(self) -> None:
        """Check all provider contracts and report."""
        recall_checks: list[tuple[str, str, bool]] = []
        precision_checks: list[tuple[str, str, bool]] = []

        # -- Recall: All concrete providers are importable ---------------------
        for abc_mod, abc_name, impl_mod, impl_name in PROVIDER_PAIRS:
            # Import ABC
            try:
                abc_cls = _import_class(abc_mod, abc_name)
                recall_checks.append((
                    f"import-abc-{abc_name}",
                    f"{abc_name} importable from {abc_mod}",
                    True,
                ))
            except Exception as e:
                recall_checks.append((
                    f"import-abc-{abc_name}",
                    f"{abc_name} import failed: {e}",
                    False,
                ))
                continue

            # Import concrete
            try:
                impl_cls = _import_class(impl_mod, impl_name)
                recall_checks.append((
                    f"import-impl-{impl_name}",
                    f"{impl_name} importable from {impl_mod}",
                    True,
                ))
            except Exception as e:
                recall_checks.append((
                    f"import-impl-{impl_name}",
                    f"{impl_name} import failed: {e}",
                    False,
                ))
                continue

            # -- Recall: Concrete is subclass of ABC ---------------------------
            is_subclass = issubclass(impl_cls, abc_cls)
            recall_checks.append((
                f"subclass-{impl_name}",
                f"{impl_name} is subclass of {abc_name}",
                is_subclass,
            ))

            # -- Recall: Concrete implements all abstract methods --------------
            abstract_methods = _get_abstract_methods(abc_cls)
            for method_name in sorted(abstract_methods):
                has_method = hasattr(impl_cls, method_name)
                if has_method:
                    # Verify it's not still abstract
                    method_obj = getattr(impl_cls, method_name)
                    is_concrete = not getattr(method_obj, "__isabstractmethod__", False)
                else:
                    is_concrete = False

                recall_checks.append((
                    f"implements-{impl_name}.{method_name}",
                    f"{impl_name} implements {method_name}()",
                    is_concrete,
                ))

            # -- Recall: Method signatures match ABC ---------------------------
            for method_name in sorted(abstract_methods):
                abc_params = _signature_params(abc_cls, method_name)
                try:
                    impl_params = _signature_params(impl_cls, method_name)
                    params_match = abc_params == impl_params
                    recall_checks.append((
                        f"signature-{impl_name}.{method_name}",
                        f"{impl_name}.{method_name}() params match ABC "
                        f"(expected {abc_params}, got {impl_params})",
                        params_match,
                    ))
                except Exception as e:
                    recall_checks.append((
                        f"signature-{impl_name}.{method_name}",
                        f"Could not inspect {impl_name}.{method_name}(): {e}",
                        False,
                    ))

        # -- Recall: ABC-only providers are importable -------------------------
        for abc_mod, abc_name in ABC_ONLY:
            try:
                _import_class(abc_mod, abc_name)
                recall_checks.append((
                    f"import-abc-{abc_name}",
                    f"{abc_name} importable from {abc_mod}",
                    True,
                ))
            except Exception as e:
                recall_checks.append((
                    f"import-abc-{abc_name}",
                    f"{abc_name} import failed: {e}",
                    False,
                ))

        # -- Precision: Incomplete subclass raises TypeError -------------------
        for abc_mod, abc_name, _, _ in PROVIDER_PAIRS:
            try:
                abc_cls = _import_class(abc_mod, abc_name)
            except Exception:
                continue

            # Create an incomplete subclass (no method overrides)
            IncompleteSubclass: type = type(  # noqa: N806
                f"Incomplete{abc_name}",
                (abc_cls,),
                {},
            )

            try:
                # Attempting to instantiate should raise TypeError because
                # abstract methods are not implemented
                IncompleteSubclass()  # type: ignore[call-arg]
                raises_error = False
            except TypeError:
                raises_error = True
            except Exception:
                # Some other error -- not what we expected but still a failure
                raises_error = False

            precision_checks.append((
                f"incomplete-raises-{abc_name}",
                f"Incomplete subclass of {abc_name} raises TypeError on instantiation",
                raises_error,
            ))

        # Also check ABC-only providers
        for abc_mod, abc_name in ABC_ONLY:
            try:
                abc_cls = _import_class(abc_mod, abc_name)
            except Exception:
                continue

            IncompleteSubclass = type(  # noqa: N806
                f"Incomplete{abc_name}",
                (abc_cls,),
                {},
            )

            try:
                IncompleteSubclass()  # type: ignore[call-arg]
                raises_error = False
            except TypeError:
                raises_error = True
            except Exception:
                raises_error = False

            precision_checks.append((
                f"incomplete-raises-{abc_name}",
                f"Incomplete subclass of {abc_name} raises TypeError on instantiation",
                raises_error,
            ))

        # -- Report (100% threshold for deterministic eval) --------------------
        passed = self.report(recall_checks, precision_checks)
        if not passed:
            sys.exit(1)

    def cleanup(self) -> None:
        """No cleanup needed for deterministic contract checks."""
        print("No cleanup needed (deterministic eval).")


if __name__ == "__main__":
    scorer = ScoreProviderContract()
    scorer.main()
