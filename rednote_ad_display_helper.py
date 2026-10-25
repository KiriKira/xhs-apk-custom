"""Build the small Android helper that hides feed ad cards after binding."""

from __future__ import annotations

import shutil
from pathlib import Path

from rednote_signature_compat import _resolve_android_jar, _resolve_d8, _run


JAVA_SOURCES = {}
JAVA_SOURCES["FeedAdDisplay.java"] = r'''package dev.kiri.xhsads;

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


JAVA_SOURCES["FeedAdDetector.java"] = r'''package dev.kiri.xhsads;

import java.lang.reflect.Field;

/**
 * Decides whether a bound discovery-feed item is an advertisement without hard-coding bean fields
 * from one build: the marker names below are read reflectively and a present-but-empty AdsInfo is
 * never enough on its own (media beans can carry an empty one).
 */
public final class FeedAdDetector {
    private static final String ADS_INFO = "adsInfo";
    private static final String[] ADS_INFO_TYPES = {"com.xingin.entities.ad.AdsInfo"};
    private static final String[] ADS_INFO_TEXT = {"id", "trackId", "adsType", "bizType"};

    private FeedAdDetector() {
    }

    public static boolean isAd(Object item) {
        if (item == null) {
            return false;
        }
        try {
            String type = item.getClass().getName();
            if (type.startsWith("com.xingin.advert.")) {
                return true;
            }
            for (int index = 0; index < ADS_INFO_TYPES.length; index++) {
                if (type.equals(ADS_INFO_TYPES[index])) {
                    return true;
                }
            }
            if (!type.startsWith("com.xingin.entities")) {
                return false;
            }
            if (flag(item, "isAd") || flag(item, "isShowAdTips")) {
                return true;
            }
            if (flag(item, "isBrand")) {
                return false;
            }
            return adsInfoPayload(value(item, ADS_INFO));
        } catch (Throwable ignored) {
            return false;
        }
    }

    /** Only a populated AdsInfo means the card really carries an ad payload. */
    private static boolean adsInfoPayload(Object adsInfo) {
        if (adsInfo == null) {
            return false;
        }
        try {
            if (flag(adsInfo, "showTag")) {
                return true;
            }
            for (int index = 0; index < ADS_INFO_TEXT.length; index++) {
                Object current = value(adsInfo, ADS_INFO_TEXT[index]);
                if (current instanceof String && ((String) current).trim().length() > 0) {
                    return true;
                }
            }
        } catch (Throwable ignored) {
        }
        return false;
    }

    private static boolean flag(Object item, String name) {
        Object current = value(item, name);
        return current instanceof Boolean && ((Boolean) current).booleanValue();
    }

    private static Object value(Object item, String name) {
        Class<?> type = item.getClass();
        for (int level = 0; level < 6 && type != null && type != Object.class; level++) {
            Field field;
            try {
                field = type.getDeclaredField(name);
            } catch (Throwable ignored) {
                type = type.getSuperclass();
                continue;
            }
            try {
                field.setAccessible(true);
                return field.get(item);
            } catch (Throwable ignored) {
                return null;
            }
        }
        return null;
    }
}
'''

JAVA_SOURCES["FeedInspector.java"] = r'''package dev.kiri.xhsads;

import android.content.Context;
import android.content.SharedPreferences;

import java.lang.reflect.Field;
import java.util.List;

/**
 * Debug-only card inspector. While the switch in "小K书设置" is on, every bound card is summarised into
 * a rotating log and long-pressing a card stores a full field dump of its bound item.
 */
public final class FeedInspector {
    private static final String PREFS = "kiri_xhs_block_words";
    private static final String KEY_ENABLED = "debug_inspect";
    private static final String KEY_DUMP = "debug_dump";
    private static final String KEY_RECENT = "debug_recent";
    private static final int MAX_RECENT_LINES = 40;
    private static final int MAX_DEPTH = 2;

    private static long checkedAt;
    private static boolean enabled;

    private FeedInspector() {
    }

    public static void onBind(final android.view.View root, final Object item) {
        try {
            if (root == null || item == null || !enabled(root.getContext())) {
                return;
            }
            store(root.getContext(), KEY_RECENT, summary(item), MAX_RECENT_LINES);
            root.setOnLongClickListener(new android.view.View.OnLongClickListener() {
                @Override
                public boolean onLongClick(android.view.View view) {
                    try {
                        store(view.getContext(), KEY_DUMP, describe(item), 200);
                        android.widget.Toast.makeText(view.getContext().getApplicationContext(),
                                "小K书：已抓取卡片信息，去「小K书设置」查看",
                                android.widget.Toast.LENGTH_SHORT).show();
                    } catch (Throwable ignored) {
                    }
                    return true;
                }
            });
        } catch (Throwable ignored) {
        }
    }

    private static boolean enabled(Context context) {
        long now = System.currentTimeMillis();
        if (now - checkedAt < 1500L) {
            return enabled;
        }
        checkedAt = now;
        try {
            enabled = prefs(context).getBoolean(KEY_ENABLED, false);
        } catch (Throwable ignored) {
            enabled = false;
        }
        return enabled;
    }

    private static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    private static void store(Context context, String key, String value, int maxLines) {
        try {
            SharedPreferences prefs = prefs(context);
            String previous = prefs.getString(key, "");
            String merged = value + "\n" + (previous == null ? "" : previous);
            String[] lines = merged.split("\n");
            StringBuilder builder = new StringBuilder();
            for (int index = 0; index < lines.length && index < maxLines; index++) {
                if (lines[index].length() == 0) {
                    continue;
                }
                builder.append(lines[index]).append('\n');
            }
            prefs.edit().putString(key, builder.toString()).apply();
        } catch (Throwable ignored) {
        }
    }

    /** One-line entry for the rotating log. */
    private static String summary(Object item) {
        StringBuilder builder = new StringBuilder();
        try {
            builder.append(item.getClass().getName()).append(" | ");
            String title = text(value(item, "displayTitle"));
            if (title.length() == 0) {
                title = text(value(item, "title"));
            }
            builder.append("title=").append(shorten(title, 40));
            builder.append(" isAd=").append(value(item, "isAd"));
            builder.append(" tips=").append(value(item, "isShowAdTips"));
            builder.append(" brand=").append(value(item, "isBrand"));
            Object ads = value(item, "adsInfo");
            builder.append(" adsInfo=").append(ads == null ? "null" : "yes");
            if (ads != null) {
                builder.append("(id=").append(shorten(text(value(ads, "id")), 12));
                builder.append(",type=").append(shorten(text(value(ads, "adsType")), 12));
                builder.append(",tag=").append(value(ads, "showTag")).append(')');
            }
        } catch (Throwable ignored) {
        }
        return builder.toString();
    }

    /** Multi-line dump used when a card is long-pressed on purpose. */
    private static String describe(Object item) {
        StringBuilder builder = new StringBuilder();
        try {
            builder.append("item: ").append(item.getClass().getName()).append('\n');
            dumpFields(item, builder, 0, "  ");
        } catch (Throwable ignored) {
        }
        return builder.toString();
    }

    private static void dumpFields(Object target, StringBuilder out, int depth, String indent) {
        if (target == null || depth > MAX_DEPTH || out.length() > 4000) {
            return;
        }
        Class<?> type = target.getClass();
        for (int step = 0; step < 3 && type != null && type != Object.class; step++) {
            Field[] fields;
            try {
                fields = type.getDeclaredFields();
            } catch (Throwable ignored) {
                return;
            }
            for (int index = 0; index < fields.length; index++) {
                Field field = fields[index];
                try {
                    field.setAccessible(true);
                    Object current = field.get(target);
                    if (current == null) {
                        continue;
                    }
                    String name = field.getName();
                    if (current instanceof String || current instanceof Number
                            || current instanceof Boolean) {
                        out.append(indent).append(name).append('=')
                                .append(shorten(String.valueOf(current), 90)).append('\n');
                    } else if (current instanceof List) {
                        out.append(indent).append(name).append("=List(")
                                .append(((List<?>) current).size()).append(")\n");
                        if (depth < MAX_DEPTH) {
                            List<?> list = (List<?>) current;
                            int limit = Math.min(list.size(), 3);
                            for (int item = 0; item < limit; item++) {
                                Object element = list.get(item);
                                if (element instanceof String) {
                                    out.append(indent).append("  - ")
                                            .append(shorten((String) element, 60)).append('\n');
                                } else if (element != null) {
                                    out.append(indent).append("  - ")
                                            .append(element.getClass().getSimpleName()).append('\n');
                                }
                            }
                        }
                    } else if (name.startsWith("adsInfo") || name.startsWith("adInfo")
                            || name.equals("noteTradeInfo")) {
                        out.append(indent).append(name).append(": ")
                                .append(current.getClass().getName()).append('\n');
                        dumpFields(current, out, depth + 1, indent + "    ");
                    }
                } catch (Throwable ignored) {
                }
            }
            type = type.getSuperclass();
        }
    }

    private static Object value(Object target, String name) {
        if (target == null) {
            return null;
        }
        Class<?> type = target.getClass();
        for (int level = 0; level < 6 && type != null && type != Object.class; level++) {
            try {
                Field field = type.getDeclaredField(name);
                field.setAccessible(true);
                return field.get(target);
            } catch (Throwable ignored) {
                type = type.getSuperclass();
            }
        }
        return null;
    }

    private static String text(Object value) {
        return value instanceof String ? ((String) value).trim() : "";
    }

    private static String shorten(String value, int limit) {
        if (value == null) {
            return "";
        }
        String trimmed = value.replace('\n', ' ').trim();
        return trimmed.length() <= limit ? trimmed : trimmed.substring(0, limit) + "…";
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

    java_files = []
    for name in sorted(JAVA_SOURCES):
        java_file = source_dir / name
        java_file.write_text(JAVA_SOURCES[name], encoding="utf-8", newline="\n")
        java_files.append(java_file)

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
        *java_files,
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
        raise RuntimeError("Java compiler did not produce the ad helper class files")

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
