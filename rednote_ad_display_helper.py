"""Build the small Android helper that hides feed ad cards after binding."""

from __future__ import annotations

import shutil
from pathlib import Path

from rednote_signature_compat import _resolve_android_jar, _resolve_d8, _run


JAVA_SOURCE = r'''package dev.kiri.xhsads;

import android.view.View;
import android.view.ViewGroup;

import java.util.WeakHashMap;

/**
 * Applies the final display state to an already-bound feed card. Call this
 * from the feed binder on the main thread, after the app has finished binding.
 */
public final class FeedAdDisplay {
    private static final WeakHashMap<View, State> STATES = new WeakHashMap<View, State>();

    private FeedAdDisplay() {
    }

    public static void apply(View root, boolean isAd) {
        if (root == null) {
            return;
        }

        if (isAd) {
            hide(root);
        } else {
            restore(root);
        }
    }

    private static void hide(View root) {
        State state = STATES.get(root);
        ViewGroup.LayoutParams params = root.getLayoutParams();

        if (state == null) {
            state = new State(root.getVisibility(), params != null, params == null ? 0 : params.height);
            STATES.put(root, state);
        } else if (!state.hasHeight && params != null) {
            // A view first hidden before it had LayoutParams can still be
            // compressed later, while retaining the first available height.
            state.height = params.height;
            state.hasHeight = true;
        }

        if (params != null && state.hasHeight) {
            params.height = 0;
            root.setLayoutParams(params);
        }
        root.setVisibility(View.GONE);
    }

    private static void restore(View root) {
        State state = STATES.remove(root);
        if (state == null) {
            // Ordinary cards, including those originally GONE, are untouched.
            return;
        }

        ViewGroup.LayoutParams params = root.getLayoutParams();
        if (params != null && state.hasHeight) {
            params.height = state.height;
            root.setLayoutParams(params);
        }
        root.setVisibility(state.visibility);
    }

    private static final class State {
        int height;
        final int visibility;
        boolean hasHeight;

        State(int visibility, boolean hasHeight, int height) {
            this.visibility = visibility;
            this.hasHeight = hasHeight;
            this.height = height;
        }
    }
}
'''


def build_ad_display_dex(work_dir: Path) -> Path:
    """Compile FeedAdDisplay.java into a min-api-21 ``classes.dex`` file."""
    work_dir = Path(work_dir)
    helper_root = work_dir / "ad-display-helper"
    if helper_root.exists():
        shutil.rmtree(helper_root)

    source_dir = helper_root / "src" / "dev" / "kiri" / "xhsads"
    classes_dir = helper_root / "classes"
    dex_dir = helper_root / "dex"
    source_dir.mkdir(parents=True)
    classes_dir.mkdir()
    dex_dir.mkdir()

    java_file = source_dir / "FeedAdDisplay.java"
    java_file.write_text(JAVA_SOURCE, encoding="utf-8", newline="\n")

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
        java_file,
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
        raise RuntimeError("Java compiler did not produce FeedAdDisplay class files")

    d8 = _resolve_d8()
    _run(
        [
            d8,
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
        raise RuntimeError("D8 did not produce ad display helper classes.dex")
    return dex
