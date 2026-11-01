"""Temporary IM transport diagnostics: log the fortuna transport callbacks.

The DM "spinner never finishes" report cannot be explained from logcat or from static analysis:
IM delivery runs through `com.xingin.fortuna.transport`, whose callbacks are pure Java but silent in
release builds. This patch inserts a `Log.i("kiri-im", ...)` call at the top of every observer method
so a device run shows whether the message reached the transport, whether the transport reported a
send, and which error (timeout / not connected / send failed) came back.

Nothing else changes: no behaviour, no state, no request. It exists to gather one logcat capture and
should not be ship-enabled.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from rednote_block_words_patch import (
    _method_calls as _calls,
    _resolve_android_jar,
    _resolve_d8,
    _run,
)

HELPER_PACKAGE = Path("dev/kiri/xhsdiag")
HELPER_CLASS = "dev.kiri.xhsdiag.ImDiag"
HELPER_DESCRIPTOR = "Ldev/kiri/xhsdiag/ImDiag;"
LOG_TAG = "kiri-im"

JAVA_SOURCE = r"""package dev.kiri.xhsdiag;

import android.util.Log;

/** Diagnostic only: prints the fortuna transport callbacks so a device run can be judged. */
public final class ImDiag {
    private static final String TAG = "kiri-im";

    private ImDiag() {
    }

    public static void send(Object envelope) {
        try {
            Log.i(TAG, "[diag] didSend envelope=" + name(envelope));
        } catch (Throwable ignored) {
        }
    }

    public static void error(Object error) {
        try {
            Log.i(TAG, "[diag] transportError " + describe(error));
        } catch (Throwable ignored) {
        }
    }

    public static void state(Object state) {
        try {
            Log.i(TAG, "[diag] state " + describe(state));
        } catch (Throwable ignored) {
        }
    }

    public static void validation(Object message, Object throwable) {
        try {
            Log.i(TAG, "[diag] validation " + describe(message) + " / " + describe(throwable));
        } catch (Throwable ignored) {
        }
    }

    public static void received(Object envelope) {
        try {
            Log.i(TAG, "[diag] didReceive envelope=" + name(envelope));
        } catch (Throwable ignored) {
        }
    }

    private static String name(Object value) {
        return value == null ? "null" : value.getClass().getName();
    }

    private static String describe(Object value) {
        if (value == null) {
            return "null";
        }
        try {
            return value.getClass().getName() + "(" + String.valueOf(value) + ")";
        } catch (Throwable ignored) {
            return value.getClass().getName();
        }
    }
}
"""

# Observer implementations of com.xingin.fortuna.transport.IFortunaTransportObserver in 9.48.1.
OBSERVER_CLASSES = ("b87.a", "b87.b", "h77.e")

# (method signature as it appears after `.method public `, register holding the payload, helper method)
METHOD_HOOKS = (
    (
        "onTransportDidSend([BLcom/xingin/fortuna/smart/SmartEnvelope;Ljava/lang/String;)V",
        "p2",
        "send",
    ),
    (
        "onTransportError(Lcom/xingin/fortuna/transport/core/TransportError;)V",
        "p1",
        "error",
    ),
    (
        "onTransportStateChanged(Lcom/xingin/fortuna/transport/core/TransportState;)V",
        "p1",
        "state",
    ),
    ("onValidationError(Ljava/lang/String;Ljava/lang/Throwable;)V", "p2", "validation"),
)


def _smali_path(decoded_dir: Path, class_name: str) -> Path:
    relative = class_name.replace(".", "/") + ".smali"
    for candidate in Path(decoded_dir).rglob(relative):
        return candidate
    raise FileNotFoundError(f"{class_name} was not found in the decoded smali tree")


def _hook_line(register: str, helper: str) -> str:
    return (
        f"    invoke-static {{{register}}}, {HELPER_DESCRIPTOR}->{helper}(Ljava/lang/Object;)V\n"
    )


def _patch_method(text: str, signature: str, register: str, helper: str) -> tuple[str, bool]:
    header = f".method public {signature}\n"
    start = text.find(header)
    if start < 0:
        return text, False
    body_start = start + len(header)
    end = text.find(".end method", body_start)
    if end < 0:
        raise ValueError(f"{signature} has no .end method")
    body = text[body_start:end]
    if "Ldev/kiri/xhsdiag/ImDiag;->" in body:
        return text, False
    # Insert before the trailing return so no earlier instruction offset shifts: these methods are
    # huge, and a one-instruction shift at the top overflows their branch offsets in dexlib2.
    marker = "    return-void\n"
    insert_at = body.rfind(marker)
    if insert_at < 0:
        raise ValueError(f"{signature} has no trailing return-void")
    patched_body = body[:insert_at] + _hook_line(register, helper) + body[insert_at:]
    return text[:body_start] + patched_body + text[end:], True


def install_im_diag(decoded_dir: Path) -> dict:
    """Insert the logging calls into every fortuna transport observer implementation."""
    patched: list[str] = []
    methods: list[str] = []
    for class_name in OBSERVER_CLASSES:
        path = _smali_path(decoded_dir, class_name)
        text = path.read_text(encoding="utf-8")
        changed = []
        for signature, register, helper in METHOD_HOOKS:
            text, ok = _patch_method(text, signature, register, helper)
            if ok:
                changed.append(f"{class_name}.{signature.split('(')[0]}")
        if changed:
            path.write_text(text, encoding="utf-8", newline="\n")
            patched.append(class_name)
            methods.extend(changed)
    if not methods:
        raise ValueError("No fortuna transport observer method was patched")
    return {
        "enabled": True,
        "helperClass": HELPER_CLASS,
        "logTag": LOG_TAG,
        "patchedClasses": patched,
        "patchedMethods": methods,
        "scope": (
            "Diagnostic only: logs the fortuna transport callbacks. No behaviour change; "
            "not intended for a normal release."
        ),
    }


def verify_compiled_im_diag(apk: Path, dex_name: str) -> dict:
    """Assert the compiled IM dex calls the diagnostics helper from every observer callback."""
    import sys
    import zipfile

    sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
    from verify_rednote_signature_compat import DexFile

    with zipfile.ZipFile(apk) as archive:
        dex = DexFile(archive.read(dex_name), dex_name)
    verified: list[str] = []
    for class_name in OBSERVER_CLASSES:
        descriptor = "L" + class_name.replace(".", "/") + ";"
        definitions = dex.class_definitions(descriptor)
        if len(definitions) != 1:
            raise ValueError(f"{dex_name} is missing observer {class_name}")
        for signature, _register, helper in METHOD_HOOKS:
            method = signature.split("(")[0]
            proto = "(" + signature.split("(", 1)[1]
            codes = [
                code
                for index, _, code in dex.method_records(definitions[0])
                if dex.method_id(index) == (descriptor, method, proto)
            ]
            if len(codes) != 1:
                raise ValueError(f"Expected one {class_name}.{method}")
            target = (HELPER_DESCRIPTOR, helper, "(Ljava/lang/Object;)V")
            if not _calls(dex, codes[0], target):
                raise ValueError(f"{class_name}.{method} does not call ImDiag.{helper}")
            verified.append(f"{class_name}.{method}")
    return {"verified": True, "dex": dex_name, "callbacks": verified}


def build_im_diag_dex(work_dir: Path) -> Path:
    """Compile the diagnostics helper into a min-api-21 classes.dex."""
    work_dir = Path(work_dir)
    root = work_dir / "im-diag-helper"
    if root.exists():
        shutil.rmtree(root)
    source_root = root / "src"
    classes_dir = root / "classes"
    dex_dir = root / "dex"
    classes_dir.mkdir(parents=True)
    dex_dir.mkdir(parents=True)

    package_dir = source_root / HELPER_PACKAGE
    package_dir.mkdir(parents=True)
    source = package_dir / "ImDiag.java"
    source.write_text(JAVA_SOURCE, encoding="utf-8", newline="\n")

    android_jar = _resolve_android_jar()
    compiler_args: list[str | Path] = [
        "-source",
        "8",
        "-target",
        "8",
        "-classpath",
        android_jar,
        "-d",
        classes_dir,
        source,
    ]
    javac = shutil.which("javac")
    if javac:
        _run([javac, *compiler_args])
    else:
        java = shutil.which("java")
        if not java:
            raise RuntimeError("Neither javac nor java was found for helper compilation")
        _run([java, "com.sun.tools.javac.Main", *compiler_args])

    class_files = sorted(classes_dir.rglob("*.class"))
    if not class_files:
        raise RuntimeError("Java compiler did not produce the IM diagnostics class")
    _run(
        [
            _resolve_d8(),
            "--min-api",
            "21",
            "--lib",
            android_jar,
            "--output",
            dex_dir,
            *class_files,
        ],
        timeout=3600,
    )
    dex = dex_dir / "classes.dex"
    if not dex.is_file():
        raise RuntimeError("D8 did not produce the IM diagnostics classes.dex")
    return dex
