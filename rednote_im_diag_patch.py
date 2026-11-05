"""Temporary IM transport diagnostics: log the longlink send path and the fortuna callbacks.

The DM "spinner never finishes" report cannot be explained from logcat or from static analysis.
Direct messages travel through `com.xingin.longlink` (a separate `:longlinkNew` process reached over
Binder) and through `com.xingin.fortuna.transport`; both are silent in release builds. This patch adds
a `Log.i("kiri-im", ...)` line at the interesting points so one device run shows how far a message got:

    svc-connected / svc-disconnected   LongLinkProxy binding to the longlink service
    send                               the client handed a message to the longlink service
    accepted                           the longlink process accepted the send
    ack / fail                         the service called the client back with a result
    fortuna-*                          the fortuna transport callbacks

Nothing else changes: no behaviour, no state, no request. It exists to gather one logcat capture and
must not be ship-enabled.
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

import android.os.Process;
import android.util.Log;

/** Diagnostic only: prints the longlink and fortuna transport steps so a device run can be judged. */
public final class ImDiag {
    private static final String TAG = "kiri-im";

    private ImDiag() {
    }

    public static void connected() {
        emit("svc-connected", null, null);
    }

    public static void disconnected() {
        emit("svc-disconnected", null, null);
    }

    public static void send(Object message) {
        emit("send", message, null);
    }

    public static void accepted(Object message) {
        emit("accepted", message, null);
    }

    public static void ack(Object result) {
        emit("ack", result, null);
    }

    public static void fail(Object code, Object reason) {
        emit("fail", code, reason);
    }

    public static void didSend(Object envelope) {
        emit("fortuna-didSend", envelope, null);
    }

    public static void state(Object state) {
        emit("fortuna-state", state, null);
    }

    public static void error(Object error) {
        emit("fortuna-error", error, null);
    }

    public static void validation(Object message, Object throwable) {
        emit("fortuna-validation", message, throwable);
    }

    private static void emit(String what, Object first, Object second) {
        try {
            StringBuilder line = new StringBuilder("[diag] ");
            line.append(what).append(" pid=").append(Process.myPid());
            if (first != null) {
                line.append(" a=").append(describe(first));
            }
            if (second != null) {
                line.append(" b=").append(describe(second));
            }
            Log.i(TAG, line.toString());
        } catch (Throwable ignored) {
        }
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

# dex entry, class (dot form), method signature after `.method public `, helper name, argument registers
HOOKS = (
    # Direct-message path: client -> Binder -> longlink process -> ack.
    (
        "classes14.dex",
        "com.xingin.longlink.remote.LongLinkProxy",
        "onServiceConnected(Landroid/content/ComponentName;Landroid/os/IBinder;)V",
        "connected",
        (),
    ),
    (
        "classes14.dex",
        "com.xingin.longlink.remote.LongLinkProxy",
        "onServiceDisconnected(Landroid/content/ComponentName;)V",
        "disconnected",
        (),
    ),
    (
        "classes14.dex",
        "com.xingin.longlink.IService$Stub$Proxy",
        "sendMessage(Lcom/xingin/longlink/message/UpMessage;Lcom/xingin/longlink/ICallback;)V",
        "send",
        ("p1",),
    ),
    (
        "classes14.dex",
        "com.xingin.longlink.service.LongLinkServiceStub",
        "sendMessage(Lcom/xingin/longlink/message/UpMessage;Lcom/xingin/longlink/ICallback;)V",
        "accepted",
        ("p1",),
    ),
    (
        "classes14.dex",
        "com.xingin.longlink.ICallback$Stub$Proxy",
        "onSuccess(Lcom/xingin/longlink/message/Result;)V",
        "ack",
        ("p1",),
    ),
    (
        "classes14.dex",
        "com.xingin.longlink.ICallback$Stub$Proxy",
        "onFailed(ILjava/lang/String;)V",
        "fail",
        ("p1", "p2"),
    ),
    # Fortuna transport callbacks, kept from the first attempt (engine-side transport).
    (
        "classes13.dex",
        "b87.a",
        "onTransportDidSend([BLcom/xingin/fortuna/smart/SmartEnvelope;Ljava/lang/String;)V",
        "didSend",
        ("p2",),
    ),
    (
        "classes13.dex",
        "b87.a",
        "onTransportError(Lcom/xingin/fortuna/transport/core/TransportError;)V",
        "error",
        ("p1",),
    ),
    (
        "classes13.dex",
        "b87.a",
        "onTransportStateChanged(Lcom/xingin/fortuna/transport/core/TransportState;)V",
        "state",
        ("p1",),
    ),
    (
        "classes13.dex",
        "b87.a",
        "onValidationError(Ljava/lang/String;Ljava/lang/Throwable;)V",
        "validation",
        ("p1", "p2"),
    ),
    (
        "classes13.dex",
        "b87.b",
        "onTransportDidSend([BLcom/xingin/fortuna/smart/SmartEnvelope;Ljava/lang/String;)V",
        "didSend",
        ("p2",),
    ),
    (
        "classes13.dex",
        "b87.b",
        "onTransportError(Lcom/xingin/fortuna/transport/core/TransportError;)V",
        "error",
        ("p1",),
    ),
    (
        "classes13.dex",
        "b87.b",
        "onTransportStateChanged(Lcom/xingin/fortuna/transport/core/TransportState;)V",
        "state",
        ("p1",),
    ),
    (
        "classes13.dex",
        "b87.b",
        "onValidationError(Ljava/lang/String;Ljava/lang/Throwable;)V",
        "validation",
        ("p1", "p2"),
    ),
    (
        "classes13.dex",
        "h77.e",
        "onTransportDidSend([BLcom/xingin/fortuna/smart/SmartEnvelope;Ljava/lang/String;)V",
        "didSend",
        ("p2",),
    ),
    (
        "classes13.dex",
        "h77.e",
        "onTransportError(Lcom/xingin/fortuna/transport/core/TransportError;)V",
        "error",
        ("p1",),
    ),
    (
        "classes13.dex",
        "h77.e",
        "onTransportStateChanged(Lcom/xingin/fortuna/transport/core/TransportState;)V",
        "state",
        ("p1",),
    ),
    (
        "classes13.dex",
        "h77.e",
        "onValidationError(Ljava/lang/String;Ljava/lang/Throwable;)V",
        "validation",
        ("p1", "p2"),
    ),
)

# Methods longer than this are hooked just before their trailing return: a one-instruction shift at
# the top of a method that large overflows dexlib2's 16-bit branch offsets while recompiling.
LARGE_METHOD_LINES = 2000


def _smali_path(decoded_dir: Path, dex_entry: str, class_name: str) -> Path:
    relative = class_name.replace(".", "/") + ".smali"
    direct = Path(decoded_dir) / "smali" / dex_entry[: -len(".dex")] / relative
    if direct.is_file():
        return direct
    for candidate in Path(decoded_dir).rglob(relative):
        return candidate
    raise FileNotFoundError(f"{class_name} was not found in the decoded smali tree ({dex_entry})")


def _helper_descriptor(count: int) -> str:
    return "(" + "Ljava/lang/Object;" * count + ")V"


def _hook_lines(helper: str, arguments: tuple[str, ...]) -> str:
    registers = ", ".join(arguments)
    return (
        f"    invoke-static {{{registers}}}, {HELPER_DESCRIPTOR}->{helper}"
        f"{_helper_descriptor(len(arguments))}\n"
    )


def _patch_method(
    text: str, signature: str, helper: str, arguments: tuple[str, ...]
) -> tuple[str, bool]:
    header = f".method public {signature}\n"
    start = text.find(header)
    if start < 0:
        return text, False
    body_start = start + len(header)
    end = text.find(".end method", body_start)
    if end < 0:
        raise ValueError(f"{signature} has no .end method")
    body = text[body_start:end]
    if f"{HELPER_DESCRIPTOR}->{helper}(" in body:
        return text, False
    hook = "\n" + _hook_lines(helper, arguments)
    instruction_lines = sum(
        1 for line in body.splitlines() if line.startswith("    ") and not line.startswith("     ")
    )
    if instruction_lines > LARGE_METHOD_LINES:
        marker = "    return-void\n"
        insert_at = body.rfind(marker)
        if insert_at < 0:
            raise ValueError(f"{signature} has no trailing return-void")
        patched = body[:insert_at] + hook + body[insert_at:]
    else:
        insert_at = -1
        for directive in (".locals ", ".registers "):
            index = body.find(directive)
            if index >= 0 and (insert_at < 0 or index < insert_at):
                insert_at = index
        if insert_at < 0:
            raise ValueError(f"{signature} has neither .locals nor .registers")
        line_end = body.find("\n", insert_at)
        if line_end < 0:
            raise ValueError(f"{signature} directive is not terminated")
        patched = body[: line_end + 1] + hook + body[line_end + 1 :]
    return text[:body_start] + patched + text[end:], True


def install_im_diag(decoded_dir: Path) -> dict:
    """Insert the logging calls into the longlink and fortuna transport entry points."""
    files: dict[Path, str] = {}
    patched_methods: list[str] = []
    touched: dict[str, set[str]] = {}
    for dex_entry, class_name, signature, helper, arguments in HOOKS:
        path = _smali_path(decoded_dir, dex_entry, class_name)
        text = files.get(path) or path.read_text(encoding="utf-8")
        text, ok = _patch_method(text, signature, helper, arguments)
        files[path] = text
        if ok:
            patched_methods.append(f"{class_name}.{signature.split('(')[0]}")
            touched.setdefault(dex_entry, set()).add(class_name)
    if not patched_methods:
        raise ValueError("No transport diagnostic hook was patched")
    for path, text in files.items():
        path.write_text(text, encoding="utf-8", newline="\n")
    return {
        "enabled": True,
        "helperClass": HELPER_CLASS,
        "logTag": LOG_TAG,
        "patchedMethods": patched_methods,
        "touchedDexEntries": sorted(touched),
        "scope": (
            "Diagnostic only: logs the longlink send path (connect/send/accepted/ack/fail) and the "
            "fortuna transport callbacks. No behaviour change; not intended for a normal release."
        ),
    }


def verify_compiled_im_diag(apk: Path, dex_entry: str) -> dict:
    """Assert every hook target that lives in one dex calls the diagnostics helper."""
    import sys
    import zipfile

    sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
    from verify_rednote_signature_compat import DexFile

    with zipfile.ZipFile(apk) as archive:
        dex = DexFile(archive.read(dex_entry), dex_entry)
    verified: list[str] = []
    for hook_dex, class_name, signature, helper, arguments in HOOKS:
        if hook_dex != dex_entry:
            continue
        descriptor = "L" + class_name.replace(".", "/") + ";"
        definitions = dex.class_definitions(descriptor)
        if len(definitions) != 1:
            raise ValueError(f"{dex_entry} is missing {class_name}")
        method = signature.split("(")[0]
        proto = "(" + signature.split("(", 1)[1]
        codes = [
            code
            for index, _, code in dex.method_records(definitions[0])
            if dex.method_id(index) == (descriptor, method, proto)
        ]
        if len(codes) != 1:
            raise ValueError(f"Expected one {class_name}.{method} in {dex_entry}")
        target = (HELPER_DESCRIPTOR, helper, _helper_descriptor(len(arguments)))
        if not _calls(dex, codes[0], target):
            raise ValueError(f"{class_name}.{method} does not call ImDiag.{helper}")
        verified.append(f"{class_name}.{method}")
    return {"verified": True, "dex": dex_entry, "callbacks": verified}


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
