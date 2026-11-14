"""Manual keyword blocking for the REDnote discovery feed, with a settings entry.

The patch adds three display-only pieces to REDnote 9.48.1 (9481803):

1. ``FeedKeywordFilter`` is called from the existing discovery-feed bind hook
   (the same hook ``--hide-feed-ads`` installs). It collects the visible text of
   the already-bound card and hides the whole card root when a user keyword
   matches, using the same ``FeedAdDisplay.apply`` display state as the ad patch.
2. ``SettingsHook.install`` is called at the end of
   ``SettingActivityV2.onCreate``. After the first layout it registers a binder
   for a private ``BlockEntry`` item and inserts that item directly below the
   ``关于小红书`` row of the settings list, so the entry sits in the settings list
   itself instead of a synthetic overlay.
3. ``BlockWordsActivity`` (declared by the builder in the manifest) stores the
   keyword list in ``SharedPreferences``.

Everything is display-only: requests, response payloads and feed items stay
unchanged, and a failure inside the helper degrades to "no entry / no filtering"
instead of touching the app's own state.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

from rednote_signature_compat import _resolve_android_jar, _resolve_d8, _run

SETTINGS_ACTIVITY = "com.xingin.matrix.setting.SettingActivityV2"
SETTINGS_ACTIVITY_DESCRIPTOR = "Lcom/xingin/matrix/setting/SettingActivityV2;"
# Obfuscated per build: the MultiType binder base was ``Lba/d;`` in 9.48.1 and is
# ``Lha/d;`` in 9.54.0 once ``Lha/c`` re-chains through it.
BINDER_BASE = "Lha/d;"
ACTIVITY_CLASS = "dev.kiri.xhsads.BlockWordsActivity"
ANDROID_NS = "http://schemas.android.com/apk/res/android"
# Obfuscated per build: 9.48.1 routed through ``Rd``, 9.54.0 through ``Vd``.
SETTINGS_ACTIVITY_LAUNCH = (
    "    invoke-static {p0, p1}, Lcom/xingin/matrix/setting/SettingActivityV2;->"
    "Vd(Lcom/xingin/matrix/setting/SettingActivityV2;Landroid/os/Bundle;)V\n"
)
SETTINGS_ACTIVITY_HOOK = (
    "\n    invoke-static {p0}, Ldev/kiri/xhsads/SettingsHook;->"
    "install(Landroid/app/Activity;)V\n"
)
# Pinned sha256 of ``SettingActivityV2.onCreate(Landroid/os/Bundle;)V`` in the
# verified REDnote 9.54.0 (9540804) APKEditor 1.4.9 / jf decode.
EXPECTED_ONCREATE_SHA = (
    "8bb0cd2b04dd64efafad5a9ceaf3cd223946b4e4910184dcd3a0d6bbd3fdc4df"
)
# Pinned sha256 of ``SettingActivityV2.onWindowFocusChanged(Z)V`` (same decode).
EXPECTED_FOCUS_SHA = (
    "2ac8ed934ffa498b8dcaecfed9c9c76dcac563d9b91995ae4630e768fbc9807e"
)
FOCUS_SUPER_CALL = (
    "    invoke-super {p0, p1}, Lcom/xingin/foundation/framework/v2/LCBActivity;->"
    "onWindowFocusChanged(Z)V\n"
)
FOCUS_ENSURE_HOOK = (
    "\n    invoke-static {p0}, Ldev/kiri/xhsads/SettingsHook;->"
    "ensure(Landroid/app/Activity;)V\n"
)

# Must match ``rednote_ad_patch.HIDE`` byte for byte, including the item-list
# accessor name (``A0()`` in 9.54.0, ``B0()`` in 9.48.1).
FEED_APPLY_BLOCK = (
    "    :rednote_feed_ad_apply\n"
    "    iget-object v0, p1, Landroidx/recyclerview/widget/RecyclerView$ViewHolder;->"
    "itemView:Landroid/view/View;\n"
    "    invoke-static {v0, v1}, Ldev/kiri/xhsads/FeedAdDisplay;->"
    "apply(Landroid/view/View;Z)V\n"
)
FEED_APPLY_BLOCK_KEYWORDS = (
    "    :rednote_feed_ad_apply\n"
    "    iget-object v0, p1, Landroidx/recyclerview/widget/RecyclerView$ViewHolder;->"
    "itemView:Landroid/view/View;\n"
    "    if-nez v1, :rednote_feed_keyword_done\n"
    "    invoke-static {v0, v2}, Ldev/kiri/xhsads/FeedKeywordFilter;->"
    "matches(Landroid/view/View;Ljava/lang/Object;)Z\n"
    "    move-result v1\n"
    "    :rednote_feed_keyword_done\n"
    "    invoke-static {v0, v1}, Ldev/kiri/xhsads/FeedAdDisplay;->"
    "apply(Landroid/view/View;Z)V\n"
)

HELPER_PACKAGE = "dev/kiri/xhsads"
SMALI_CLASSES = {
    "BlockViewHolder.smali": r""".class public final Ldev/kiri/xhsads/BlockViewHolder;
.super Landroidx/recyclerview/widget/RecyclerView$ViewHolder;


# direct methods
.method public constructor <init>(Landroid/view/View;)V
    .locals 0

    invoke-direct {p0, p1}, Landroidx/recyclerview/widget/RecyclerView$ViewHolder;-><init>(Landroid/view/View;)V

    return-void
.end method
""",
    "BlockBinder.smali": r""".class public final Ldev/kiri/xhsads/BlockBinder;
.super Lha/d;


# direct methods
.method public constructor <init>()V
    .locals 0

    invoke-direct {p0}, Lha/d;-><init>()V

    return-void
.end method


# virtual methods
.method public onBindViewHolder(Landroidx/recyclerview/widget/RecyclerView$ViewHolder;Ljava/lang/Object;)V
    .locals 1

    iget-object v0, p1, Landroidx/recyclerview/widget/RecyclerView$ViewHolder;->itemView:Landroid/view/View;

    invoke-static {v0}, Ldev/kiri/xhsads/BlockRow;->bind(Landroid/view/View;)V

    return-void
.end method

.method public onCreateViewHolder(Landroid/content/Context;Landroid/view/ViewGroup;)Landroidx/recyclerview/widget/RecyclerView$ViewHolder;
    .locals 4

    invoke-static {p1}, Ldev/kiri/xhsads/BlockRow;->create(Landroid/content/Context;)Landroid/view/View;

    move-result-object v0

    new-instance v1, Landroidx/recyclerview/widget/RecyclerView$LayoutParams;

    const/4 v2, -0x1

    const/4 v3, -0x2

    invoke-direct {v1, v2, v3}, Landroidx/recyclerview/widget/RecyclerView$LayoutParams;-><init>(II)V

    invoke-virtual {v0, v1}, Landroid/view/View;->setLayoutParams(Landroid/view/ViewGroup$LayoutParams;)V

    new-instance v1, Ldev/kiri/xhsads/BlockViewHolder;

    invoke-direct {v1, v0}, Ldev/kiri/xhsads/BlockViewHolder;-><init>(Landroid/view/View;)V

    return-object v1
.end method
""",
}

JAVA_SOURCES = {
    "BlockSettings.java": r"""package dev.kiri.xhsads;

import android.content.Context;
import android.content.SharedPreferences;

/** Keyword list storage plus tiny diagnostics shared by the page and the feed filter. */
public final class BlockSettings {
    private static final String PREFS = "kiri_xhs_block_words";
    private static final String KEY = "words";
    private static final String KEY_SAVED_AT = "saved_at";
    private static final String KEY_SEEN = "diag_seen";
    private static final String KEY_HIT = "diag_hit";
    private static final String KEY_WORDS = "diag_words";
    private static final String KEY_SAMPLE = "diag_sample";
    private static final String LOG_TAG = "kiri-block";

    private static volatile String cachedRaw;
    private static volatile String[] cachedWords;
    private static int seen;
    private static int hits;

    private BlockSettings() {
    }

    public static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public static String raw(Context context) {
        try {
            String value = prefs(context).getString(KEY, "");
            return value == null ? "" : value;
        } catch (Throwable ignored) {
            return "";
        }
    }

    public static String[] words(Context context) {
        String value = raw(context);
        String[] cached = cachedWords;
        if (cached != null && value.equals(cachedRaw)) {
            return cached;
        }
        String[] parsed = parse(value);
        cachedRaw = value;
        cachedWords = parsed;
        return parsed;
    }

    public static void save(Context context, String value) {
        String normalized = value == null ? "" : value;
        prefs(context)
                .edit()
                .putString(KEY, normalized)
                .putLong(KEY_SAVED_AT, System.currentTimeMillis())
                .putInt(KEY_WORDS, parse(normalized).length)
                .apply();
        cachedRaw = normalized;
        cachedWords = parse(normalized);
    }

    public static String[] parse(String value) {
        java.util.ArrayList<String> out = new java.util.ArrayList<String>();
        if (value != null) {
            String[] parts = value.split("[\n\r,，、;；]+");
            for (int index = 0; index < parts.length; index++) {
                String word = parts[index].trim();
                if (word.length() > 0 && !out.contains(word)) {
                    out.add(word);
                }
            }
        }
        return out.toArray(new String[out.size()]);
    }

    /** Called by the feed filter for every bound card so the page can show what happened. */
    public static synchronized void record(Context context, String sample, boolean hit, int wordCount) {
        try {
            seen++;
            if (hit) {
                hits++;
            }
            String text = sample == null ? "" : sample.trim();
            if (text.length() > 300) {
                text = text.substring(0, 300);
            }
            boolean write = seen <= 3 || hit || seen % 15 == 0;
            if (!write) {
                return;
            }
            prefs(context)
                    .edit()
                    .putInt(KEY_SEEN, seen)
                    .putInt(KEY_HIT, hits)
                    .putInt(KEY_WORDS, wordCount)
                    .putString(KEY_SAMPLE, text)
                    .apply();
            if (seen <= 3 || hit) {
                android.util.Log.i(LOG_TAG, "card#" + seen + " words=" + wordCount
                        + " hit=" + hit + " text=" + text);
            }
        } catch (Throwable ignored) {
        }
    }

    public static String diagnostics(Context context) {
        try {
            SharedPreferences prefs = prefs(context);
            int words = prefs.getInt(KEY_WORDS, parse(raw(context)).length);
            long savedAt = prefs.getLong(KEY_SAVED_AT, 0L);
            String saved = savedAt == 0L ? "未保存过" : "已保存 " + words + " 个屏蔽词";
            String sample = prefs.getString(KEY_SAMPLE, "");
            if (sample == null) {
                sample = "";
            }
            return saved
                    + "\n已检查卡片 " + prefs.getInt(KEY_SEEN, 0) + " 张，命中 "
                    + prefs.getInt(KEY_HIT, 0) + " 张"
                    + "\n最近一张卡片的可见文本：\n"
                    + (sample.length() == 0 ? "(无)" : sample);
        } catch (Throwable ignored) {
            return "";
        }
    }
}
""",
    "FeedKeywordFilter.java": r"""package dev.kiri.xhsads;

import android.view.View;

import java.lang.reflect.Field;
import java.util.Locale;

/**
 * Decides whether an already-bound feed card matches a blocked keyword. The bound item is handed over
 * by the feed hook, so no view-hierarchy lookup is needed; only the note title is compared.
 */
public final class FeedKeywordFilter {
    private static final String[] TITLE_FIELDS = {"displayTitle", "title"};

    private FeedKeywordFilter() {
    }

    public static boolean matches(View root, Object item) {
        boolean hit = false;
        String title = "";
        try {
            String[] words = BlockSettings.words(root.getContext());
            title = titleOf(item);
            if (words.length > 0 && title.length() > 0) {
                hit = containsAny(title, words);
            }
            BlockSettings.record(root.getContext(), title, hit, words.length);
        } catch (Throwable ignored) {
        }
        return hit;
    }

    private static boolean containsAny(String title, String[] words) {
        String lower = title.toLowerCase(Locale.ROOT);
        String dense = compact(lower);
        for (int index = 0; index < words.length; index++) {
            String needle = words[index].toLowerCase(Locale.ROOT);
            if (needle.length() == 0) {
                continue;
            }
            if (lower.contains(needle)) {
                return true;
            }
            String denseNeedle = compact(needle);
            if (denseNeedle.length() > 0 && dense.contains(denseNeedle)) {
                return true;
            }
        }
        return false;
    }

    /** Drops separators so "日本 签证" and "日本签证" compare equal. */
    private static String compact(String value) {
        StringBuilder builder = new StringBuilder(value.length());
        for (int index = 0; index < value.length(); index++) {
            char current = value.charAt(index);
            if (Character.isWhitespace(current) || current == '\u3000' || current == '\u00a0'
                    || current == '·' || current == '-' || current == '_' || current == '/') {
                continue;
            }
            builder.append(current);
        }
        return builder.toString();
    }

    /** The note title only: the displayed title, else the raw title. */
    private static String titleOf(Object item) {
        if (item == null) {
            return "";
        }
        try {
            for (int index = 0; index < TITLE_FIELDS.length; index++) {
                Object value = value(item, TITLE_FIELDS[index]);
                if (value instanceof String) {
                    String title = ((String) value).trim();
                    if (title.length() > 0) {
                        return title;
                    }
                }
            }
        } catch (Throwable ignored) {
        }
        return "";
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
""",
    "BlockEntry.java": r"""package dev.kiri.xhsads;

/** Marker item inserted into the settings list; rendered by {@code BlockBinder}. */
public final class BlockEntry {
    public BlockEntry() {
    }

    @Override
    public String toString() {
        return "kiri-block-entry";
    }
}
""",
    "BlockRow.java": r"""package dev.kiri.xhsads;

import android.content.Context;
import android.content.Intent;
import android.graphics.Typeface;
import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Builds and binds the "小K书设置" settings row without any server layout. */
public final class BlockRow {
    private BlockRow() {
    }

    public static View create(Context context) {
        LinearLayout row = new LinearLayout(context);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        int padding = dp(context, 16);
        row.setPadding(padding, 0, padding, 0);
        row.setMinimumHeight(dp(context, 52));
        try {
            row.setBackground(context.getDrawable(
                    android.R.drawable.list_selector_background));
        } catch (Throwable ignored) {
        }

        LinearLayout column = new LinearLayout(context);
        column.setOrientation(LinearLayout.VERTICAL);
        column.setLayoutParams(new LinearLayout.LayoutParams(
                0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        column.setTag("kiri-block-column");
        row.addView(column);

        TextView title = new TextView(context);
        title.setText("小K书设置");
        title.setTextSize(16f);
        title.setTypeface(Typeface.DEFAULT);
        title.setTag("kiri-block-title");
        column.addView(title);

        TextView subtitle = new TextView(context);
        subtitle.setTextSize(12f);
        subtitle.setAlpha(0.6f);
        subtitle.setTag("kiri-block-subtitle");
        column.addView(subtitle);

        TextView arrow = new TextView(context);
        arrow.setText("›");
        arrow.setTextSize(20f);
        arrow.setAlpha(0.4f);
        row.addView(arrow);

        bind(row);
        row.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                open(view.getContext());
            }
        });
        return row;
    }

    public static void bind(View row) {
        try {
            View subtitle = row.findViewWithTag("kiri-block-subtitle");
            if (subtitle instanceof TextView) {
                int count = BlockSettings.words(row.getContext()).length;
                ((TextView) subtitle).setText(
                        count == 0 ? "自定义屏蔽词，当前未设置" : "自定义屏蔽词，已设置 " + count + " 个");
            }
            row.setOnClickListener(new View.OnClickListener() {
                @Override
                public void onClick(View view) {
                    open(view.getContext());
                }
            });
        } catch (Throwable ignored) {
        }
    }

    private static void open(Context context) {
        try {
            Intent intent = new Intent(context, BlockWordsActivity.class);
            if (!(context instanceof android.app.Activity)) {
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            }
            context.startActivity(intent);
        } catch (Throwable ignored) {
        }
    }

    private static int dp(Context context, int value) {
        return (int) (value * context.getResources().getDisplayMetrics().density + 0.5f);
    }
}
""",
    "BlockWordsActivity.java": r"""package dev.kiri.xhsads;

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

/** Settings page reached from "小K书设置" in the settings list. */
public final class BlockWordsActivity extends Activity {
    private static final String KEY_DEBUG = "debug_inspect";
    private static final String KEY_DUMP = "debug_dump";
    private static final String KEY_RECENT = "debug_recent";

    private EditText input;
    private EditText outerInput;
    private EditText innerInput;
    private TextView diagnostics;
    private TextView columnDiagnostics;
    private TextView captureLog;
    private Button debugToggle;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        setTitle("小K书设置");

        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(Color.WHITE);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        int padding = dp(16);
        root.setPadding(padding, padding, padding, padding);
        scroll.addView(root, new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView hint = new TextView(this);
        hint.setText("每行一个屏蔽词（也支持逗号、顿号分隔）。\n"
                + "只有笔记标题命中任意一个词时，整张卡片才会被隐藏。\n"
                + "匹配不区分大小写，正文、作者、标签和点赞数都不参与。");
        hint.setTextSize(13f);
        hint.setTextColor(Color.rgb(0x40, 0x40, 0x40));
        hint.setBackgroundColor(Color.rgb(0xF2, 0xF2, 0xF2));
        hint.setPadding(dp(10), dp(10), dp(10), dp(10));
        hint.setLineSpacing(dp(3), 1f);
        root.addView(hint, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        diagnostics = new TextView(this);
        diagnostics.setTextSize(11f);
        diagnostics.setTextColor(Color.rgb(0x80, 0x80, 0x80));
        diagnostics.setPadding(0, dp(8), 0, dp(8));
        diagnostics.setText(BlockSettings.diagnostics(this));
        root.addView(diagnostics, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        debugToggle = new Button(this);
        debugToggle.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                boolean next = !BlockSettings.prefs(BlockWordsActivity.this)
                        .getBoolean(KEY_DEBUG, false);
                BlockSettings.prefs(BlockWordsActivity.this)
                        .edit().putBoolean(KEY_DEBUG, next).apply();
                refreshDebug();
                Toast.makeText(BlockWordsActivity.this,
                        next ? "已开启卡片抓取：信息流里长按任意卡片" : "已关闭卡片抓取",
                        Toast.LENGTH_SHORT).show();
            }
        });
        root.addView(debugToggle, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        input = new EditText(this);
        input.setGravity(Gravity.TOP | Gravity.START);
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        input.setTextColor(Color.BLACK);
        input.setHintTextColor(Color.rgb(0x99, 0x99, 0x99));
        input.setHint("例如：日本签证\n买一送一");
        input.setText(BlockSettings.raw(this));
        LinearLayout.LayoutParams inputParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(170));
        inputParams.topMargin = dp(8);
        inputParams.bottomMargin = dp(8);
        root.addView(input, inputParams);

        LinearLayout buttons = new LinearLayout(this);
        buttons.setOrientation(LinearLayout.HORIZONTAL);

        Button clear = new Button(this);
        clear.setText("清空");
        clear.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                input.setText("");
            }
        });
        buttons.addView(clear, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        Button save = new Button(this);
        save.setText("保存");
        save.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                BlockSettings.save(BlockWordsActivity.this, input.getText().toString());
                int count = BlockSettings.words(BlockWordsActivity.this).length;
                Toast.makeText(BlockWordsActivity.this,
                        count == 0 ? "已清空屏蔽词" : "已保存 " + count + " 个屏蔽词",
                        Toast.LENGTH_SHORT).show();
                refreshDiagnostics();
            }
        });
        buttons.addView(save, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        Button clearLog = new Button(this);
        clearLog.setText("清空抓取");
        clearLog.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                BlockSettings.prefs(BlockWordsActivity.this).edit()
                        .remove(KEY_DUMP).remove(KEY_RECENT).apply();
                refreshDebug();
            }
        });
        buttons.addView(clearLog, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        root.addView(buttons, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        // ---- feed column configuration ----
        TextView columnTitle = new TextView(this);
        columnTitle.setText("信息流列数");
        columnTitle.setTextSize(14f);
        columnTitle.setTextColor(Color.BLACK);
        LinearLayout.LayoutParams columnTitleParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        columnTitleParams.topMargin = dp(18);
        root.addView(columnTitle, columnTitleParams);

        TextView columnHint = new TextView(this);
        columnHint.setText("外屏＝折叠后的窄屏，内屏＝展开后的大屏。\\n"
                + "这里填的是默认列数（打开信息流时显示几列）。\\n"
                + "双指捏合在其基础上各上下 1 列，范围 2–5 列。");
        columnHint.setTextSize(12f);
        columnHint.setTextColor(Color.rgb(0x60, 0x60, 0x60));
        columnHint.setLineSpacing(dp(3), 1f);
        LinearLayout.LayoutParams columnHintParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        columnHintParams.topMargin = dp(4);
        root.addView(columnHint, columnHintParams);

        LinearLayout columnRow = new LinearLayout(this);
        columnRow.setOrientation(LinearLayout.HORIZONTAL);
        LinearLayout.LayoutParams columnRowParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        columnRowParams.topMargin = dp(8);
        root.addView(columnRow, columnRowParams);

        TextView outerLabel = new TextView(this);
        outerLabel.setText("外屏默认");
        outerLabel.setTextSize(13f);
        outerLabel.setTextColor(Color.BLACK);
        columnRow.addView(outerLabel, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        outerInput = new EditText(this);
        outerInput.setInputType(InputType.TYPE_CLASS_NUMBER);
        outerInput.setText(String.valueOf(ColumnSettings.outerMax(this)));
        outerInput.setGravity(Gravity.CENTER);
        columnRow.addView(outerInput, new LinearLayout.LayoutParams(dp(56),
                ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView columnUnit = new TextView(this);
        columnUnit.setText("列   内屏默认");
        columnUnit.setTextSize(13f);
        columnUnit.setTextColor(Color.BLACK);
        columnRow.addView(columnUnit, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        innerInput = new EditText(this);
        innerInput.setInputType(InputType.TYPE_CLASS_NUMBER);
        innerInput.setText(String.valueOf(ColumnSettings.innerMax(this)));
        innerInput.setGravity(Gravity.CENTER);
        columnRow.addView(innerInput, new LinearLayout.LayoutParams(dp(56),
                ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView innerUnit = new TextView(this);
        innerUnit.setText("列");
        innerUnit.setTextSize(13f);
        innerUnit.setTextColor(Color.BLACK);
        columnRow.addView(innerUnit, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        LinearLayout columnButtons = new LinearLayout(this);
        columnButtons.setOrientation(LinearLayout.HORIZONTAL);
        LinearLayout.LayoutParams columnButtonsParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        columnButtonsParams.topMargin = dp(8);
        root.addView(columnButtons, columnButtonsParams);

        Button saveColumns = new Button(this);
        saveColumns.setText("保存列数");
        saveColumns.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                saveColumnInputs();
                Toast.makeText(BlockWordsActivity.this,
                        "已保存：外屏默认 " + ColumnSettings.outerMax(BlockWordsActivity.this)
                                + " 列，内屏最多 " + ColumnSettings.innerMax(BlockWordsActivity.this)
                                + " 列（返回信息流生效）",
                        Toast.LENGTH_LONG).show();
                refreshDiagnostics();
            }
        });
        columnButtons.addView(saveColumns, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        Button exportLog = new Button(this);
        exportLog.setText("导出诊断 log");
        exportLog.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                exportDiagnosticLog();
            }
        });
        columnButtons.addView(exportLog, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        Button resetColumns = new Button(this);
        resetColumns.setText("恢复默认");
        resetColumns.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                ColumnSettings.save(BlockWordsActivity.this, 4, 5);
                outerInput.setText("4");
                innerInput.setText("5");
                refreshDiagnostics();
            }
        });
        columnButtons.addView(resetColumns, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        columnDiagnostics = new TextView(this);
        columnDiagnostics.setTextSize(11f);
        columnDiagnostics.setTextColor(Color.rgb(0x40, 0x40, 0x40));
        columnDiagnostics.setBackgroundColor(Color.rgb(0xF2, 0xF7, 0xFF));
        columnDiagnostics.setPadding(dp(8), dp(8), dp(8), dp(8));
        columnDiagnostics.setTextIsSelectable(true);
        LinearLayout.LayoutParams columnDiagParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        columnDiagParams.topMargin = dp(8);
        root.addView(columnDiagnostics, columnDiagParams);

        captureLog = new TextView(this);
        captureLog.setTextSize(10f);
        captureLog.setTextColor(Color.rgb(0x33, 0x33, 0x33));
        captureLog.setBackgroundColor(Color.rgb(0xF7, 0xF7, 0xF7));
        captureLog.setPadding(dp(8), dp(8), dp(8), dp(8));
        captureLog.setTextIsSelectable(true);
        LinearLayout.LayoutParams logParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        logParams.topMargin = dp(8);
        root.addView(captureLog, logParams);

        setContentView(scroll);
        refreshDebug();
    }

    @Override
    protected void onResume() {
        super.onResume();
        refreshDiagnostics();
        refreshDebug();
    }

    /** Leaving the page keeps whatever is typed, so a missed 保存 tap cannot lose the list. */
    @Override
    protected void onPause() {
        super.onPause();
        try {
            String current = input == null ? "" : input.getText().toString();
            if (!current.equals(BlockSettings.raw(this))) {
                BlockSettings.save(this, current);
            }
        } catch (Throwable ignored) {
        }
    }

    private void refreshDiagnostics() {
        try {
            if (diagnostics != null) {
                diagnostics.setText(BlockSettings.diagnostics(this));
            }
            refreshColumnDiagnostics();
        } catch (Throwable ignored) {
        }
    }

    private void refreshColumnDiagnostics() {
        try {
            if (columnDiagnostics != null) {
                columnDiagnostics.setText(ColumnSettings.screenDescription(this)
                        + "\n\n最近判定记录：\n"
                        + tailOrNone(ColumnSettings.log(this), 12));
            }
        } catch (Throwable ignored) {
        }
    }

    private static String tailOrNone(String value, int maxLines) {
        if (value == null || value.length() == 0) {
            return "(还没有，去信息流捏合一下)";
        }
        String[] lines = value.split("\n");
        StringBuilder builder = new StringBuilder();
        int start = Math.max(0, lines.length - maxLines);
        for (int index = start; index < lines.length; index++) {
            builder.append(lines[index]).append('\n');
        }
        return builder.toString().trim();
    }

    private void saveColumnInputs() {
        try {
            int outer = parseInt(outerInput == null ? null : outerInput.getText().toString(), 4);
            int inner = parseInt(innerInput == null ? null : innerInput.getText().toString(), 5);
            ColumnSettings.save(this, outer, inner);
            if (outerInput != null) {
                outerInput.setText(String.valueOf(ColumnSettings.outerMax(this)));
            }
            if (innerInput != null) {
                innerInput.setText(String.valueOf(ColumnSettings.innerMax(this)));
            }
        } catch (Throwable ignored) {
        }
    }

    private static int parseInt(String value, int fallback) {
        try {
            int parsed = Integer.parseInt(value.trim());
            if (parsed < 1) {
                return 1;
            }
            return parsed > 9 ? 9 : parsed;
        } catch (Throwable ignored) {
            return fallback;
        }
    }

    /**
     * Writes one plain-text report to the app's external files dir and offers it
     * through the system share sheet, so the owner never has to pull logcat.
     */
    private void exportDiagnosticLog() {
        try {
            StringBuilder body = new StringBuilder();
            body.append("小K书信息流列数诊断\n")
                    .append("时间：").append(new java.util.Date().toString()).append('\n')
                    .append('\n').append(ColumnSettings.screenDescription(this)).append('\n')
                    .append("\n=== 判定记录（最新在前）===\n")
                    .append(tailOrNone(ColumnSettings.log(this), 200)).append('\n')
                    .append("\n=== 屏蔽词诊断 ===\n")
                    .append(BlockSettings.diagnostics(this)).append('\n')
                    .append("\n=== 卡片抓取 ===\n")
                    .append(BlockSettings.prefs(this).getString(KEY_RECENT, "(无)")).append('\n');

            java.io.File dir = getExternalFilesDir(null);
            if (dir == null) {
                dir = getFilesDir();
            }
            java.io.File out = new java.io.File(dir,
                    "xiaokshu-columns-" + System.currentTimeMillis() + ".txt");
            java.io.FileOutputStream stream = new java.io.FileOutputStream(out);
            try {
                stream.write(body.toString().getBytes("UTF-8"));
            } finally {
                stream.close();
            }

            android.content.Intent share = new android.content.Intent(
                    android.content.Intent.ACTION_SEND);
            share.setType("text/plain");
            share.putExtra(android.content.Intent.EXTRA_SUBJECT, "小K书列数诊断");
            share.putExtra(android.content.Intent.EXTRA_TEXT, body.toString());
            share.putExtra(android.content.Intent.EXTRA_STREAM,
                    android.net.Uri.fromFile(out));
            share.addFlags(android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION);
            startActivity(android.content.Intent.createChooser(share, "导出诊断 log"));
            Toast.makeText(this, "已生成：" + out.getAbsolutePath(),
                    Toast.LENGTH_LONG).show();
        } catch (Throwable error) {
            Toast.makeText(this, "导出失败：" + error, Toast.LENGTH_LONG).show();
        }
    }

    private void refreshDebug() {
        try {
            boolean enabled = BlockSettings.prefs(this).getBoolean(KEY_DEBUG, false);
            if (debugToggle != null) {
                debugToggle.setText(enabled
                        ? "卡片抓取：已开启（去信息流长按卡片）"
                        : "卡片抓取：已关闭（点此开启）");
            }
            if (captureLog != null) {
                String dump = BlockSettings.prefs(this).getString(KEY_DUMP, "");
                String recent = BlockSettings.prefs(this).getString(KEY_RECENT, "");
                StringBuilder builder = new StringBuilder();
                builder.append("=== 长按抓取的卡片 ===\n")
                        .append(dump == null || dump.length() == 0 ? "(还没有)" : dump)
                        .append("\n=== 最近绑定的卡片 ===\n")
                        .append(recent == null || recent.length() == 0 ? "(还没有)" : recent);
                captureLog.setText(builder.toString());
            }
        } catch (Throwable ignored) {
        }
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }
}
""",
    "ColumnSettings.java": r"""package dev.kiri.xhsads;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Build;
import android.util.DisplayMetrics;

/**
 * Runtime column table for the feed grid, editable from 小K书设置.
 *
 * The patched {@code et.n.e(int)} hands the width band ordinal and the pinch
 * ordinal to {@link #spanFor(int, int)} instead of using a baked-in table, so the
 * outer/inner maxima can be changed on the device without rebuilding the APK.
 * Every decision is recorded together with the measured width so the exported log
 * shows exactly which band this screen landed in.
 *
 * Band ordinals follow {@code et.n$d}: TINNY=0, SMALL=1, MIDDLE=2, BIG=3, LAGE=4.
 * Pinch ordinals follow {@code et.n$c}: ZOOM_IN=0, NORMAL=1, ZOOM_OUT=2.
 */
public final class ColumnSettings {
    private static final String PREFS = "kiri_xhs_columns";
    private static final String KEY_OUTER = "outer_max";
    private static final String KEY_INNER = "inner_max";
    private static final String KEY_LOG = "decision_log";
    private static final String LOG_TAG = "DynamicColumnFitWidth";

    private static final int DEFAULT_OUTER = 2;
    private static final int DEFAULT_INNER = 4;
    private static final int LOG_LIMIT = 4000;

    /** Last decision, mirrored for the settings page. */
    private static volatile String lastDecision = "";

    private ColumnSettings() {
    }

    public static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public static int outerMax(Context context) {
        try {
            return clamp(prefs(context).getInt(KEY_OUTER, DEFAULT_OUTER));
        } catch (Throwable ignored) {
            return DEFAULT_OUTER;
        }
    }

    public static int innerMax(Context context) {
        try {
            return clamp(prefs(context).getInt(KEY_INNER, DEFAULT_INNER));
        } catch (Throwable ignored) {
            return DEFAULT_INNER;
        }
    }

    public static void save(Context context, int outer, int inner) {
        try {
            prefs(context).edit()
                    .putInt(KEY_OUTER, clamp(outer))
                    .putInt(KEY_INNER, clamp(inner))
                    .apply();
        } catch (Throwable ignored) {
        }
    }

    private static int clamp(int value) {
        if (value < 1) {
            return 1;
        }
        return value > 9 ? 9 : value;
    }

    /**
     * Called from the patched {@code et.n.e(int)}. Must never throw: the feed reads
     * this on every layout pass.
     *
     * <p>There is no context argument in {@code e(int)}, so the two maxima are read
     * through {@link ApplicationHolder}, which {@code et.n.f(Context)} fills in.
     *
     * @param band  0=TINNY 1=SMALL 2=MIDDLE 3=BIG 4=LAGE
     * @param pinch 0=ZOOM_IN 1=NORMAL 2=ZOOM_OUT
     */
    public static int spanFor(int band, int pinch) {
        try {
            Context context = ApplicationHolder.get();
            int outer = context == null ? DEFAULT_OUTER : outerMax(context);
            int inner = context == null ? DEFAULT_INNER : innerMax(context);
            int columns = resolve(band, pinch, outer, inner);
            record(context, band, pinch, columns, outer, inner);
            return columns;
        } catch (Throwable ignored) {
            return 2;
        }
    }

    /** Called from the patched {@code et.n.f(Context)} so prefs are reachable. */
    public static void remember(Context context) {
        ApplicationHolder.install(context);
    }

    /**
     * Mirror of the Python {@code band_counts} in rednote_dynamic_columns_patch.py.
     *
     * The setting is the default column count, not a hard ceiling: one pinch step
     * moves one column either way and the result stays inside 2..5.
     */
    static int resolve(int band, int pinch, int outer, int inner) {
        if (band == 0) {
            return 1;                       // cover display: single column
        }
        int base = (band == 1 || band == 2) ? outer : inner;   // SMALL/MIDDLE vs BIG/LAGE
        if (pinch == 2) {                   // ZOOM_OUT
            return Math.max(2, base - 1);
        }
        if (pinch == 0) {                   // ZOOM_IN
            return Math.min(5, base + 1);
        }
        return base;                        // NORMAL
    }

    public static String bandName(int band) {
        switch (band) {
            case 0:
                return "TINNY";
            case 1:
                return "SMALL";
            case 2:
                return "MIDDLE";
            case 3:
                return "BIG";
            case 4:
                return "LAGE";
            default:
                return "band" + band;
        }
    }

    public static String pinchName(int pinch) {
        switch (pinch) {
            case 0:
                return "ZOOM_IN";
            case 1:
                return "NORMAL";
            case 2:
                return "ZOOM_OUT";
            default:
                return "pinch" + pinch;
        }
    }

    private static void record(Context context, int band, int pinch, int columns,
                               int outer, int inner) {
        try {
            String line = bandName(band) + "/" + pinchName(pinch) + " -> " + columns
                    + " 列 (外" + outer + " 内" + inner + ")";
            lastDecision = line;
            android.util.Log.i(LOG_TAG, "spanCount=" + columns + " " + line);
            if (context == null) {
                return;
            }
            SharedPreferences prefs = prefs(context);
            String existing = prefs.getString(KEY_LOG, "");
            if (existing == null) {
                existing = "";
            }
            StringBuilder builder = new StringBuilder(existing.length() + line.length() + 8);
            builder.append(line).append('\n').append(existing);
            String value = builder.toString();
            if (value.length() > LOG_LIMIT) {
                value = value.substring(0, LOG_LIMIT);
            }
            prefs.edit().putString(KEY_LOG, value).apply();
        } catch (Throwable ignored) {
        }
    }

    public static String lastDecision() {
        return lastDecision;
    }

    public static String log(Context context) {
        try {
            String value = prefs(context).getString(KEY_LOG, "");
            return value == null ? "" : value;
        } catch (Throwable ignored) {
            return "";
        }
    }

    public static void clearLog(Context context) {
        try {
            prefs(context).edit().remove(KEY_LOG).apply();
        } catch (Throwable ignored) {
        }
    }

    /** Human-readable screen sizes, so the log explains the measured widths. */
    public static String screenDescription(Context context) {
        try {
            StringBuilder builder = new StringBuilder();
            DisplayMetrics metrics = context.getResources().getDisplayMetrics();
            builder.append("当前屏幕：").append(metrics.widthPixels).append('×')
                    .append(metrics.heightPixels).append(" px, density=")
                    .append(metrics.density).append(", ")
                    .append(Math.round(metrics.widthPixels / metrics.density))
                    .append('×')
                    .append(Math.round(metrics.heightPixels / metrics.density))
                    .append(" dp");
            builder.append('\n').append("设备：").append(Build.MANUFACTURER)
                    .append(' ').append(Build.MODEL)
                    .append(" (Android ").append(Build.VERSION.RELEASE).append(')');
            builder.append('\n').append("配置：外屏默认 ").append(outerMax(context))
                    .append(" 列，内屏默认 ").append(innerMax(context)).append(" 列");
            String last = lastDecision;
            builder.append('\n').append("最近一次判定：")
                    .append(last == null || last.length() == 0 ? "(还没有)" : last);
            return builder.toString();
        } catch (Throwable ignored) {
            return "";
        }
    }
}
""",
    "ApplicationHolder.java": r"""package dev.kiri.xhsads;

import android.content.Context;

/** Holds the application context so helper classes reachable from smali can read prefs. */
public final class ApplicationHolder {
    private static volatile Context application;

    private ApplicationHolder() {
    }

    public static void install(Context context) {
        if (context == null) {
            return;
        }
        try {
            Context app = context.getApplicationContext();
            application = app == null ? context : app;
        } catch (Throwable ignored) {
        }
    }

    public static Context get() {
        return application;
    }
}
""",
    "SettingsHook.java": r"""package dev.kiri.xhsads;

import android.app.Activity;
import android.view.View;
import android.view.ViewGroup;

import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.List;
import java.util.WeakHashMap;

/**
 * Inserts the "小K书设置" row into the settings list. The settings adapter's
 * registration/read/set APIs are obfuscated in this build, so every access is
 * resolved by signature and every failure degrades to "no row".
 */
public final class SettingsHook {
    private static final String ADAPTER_CLASS = "com.drakeet.multitype.MultiTypeAdapter";
    private static final String RECYCLER_CLASS = "androidx.recyclerview.widget.RecyclerView";
    private static final String BINDER_CLASS = "dev.kiri.xhsads.BlockBinder";
    private static final String ABOUT_TITLE = "关于小红书";
    private static final int MAX_ATTEMPTS = 8;
    private static final long RETRY_DELAY_MS = 250L;

    private static final WeakHashMap<Activity, Object> INSTALLED =
            new WeakHashMap<Activity, Object>();
    private static final WeakHashMap<Object, Object> REGISTERED =
            new WeakHashMap<Object, Object>();

    private SettingsHook() {
    }

    public static void install(final Activity activity) {
        try {
            if (activity == null) {
                return;
            }
            synchronized (INSTALLED) {
                if (INSTALLED.containsKey(activity)) {
                    return;
                }
                INSTALLED.put(activity, Boolean.TRUE);
            }
            schedule(activity, 0);
            verifyLater(activity, 1500L);
            verifyLater(activity, 4000L);
        } catch (Throwable ignored) {
        }
    }

    /**
     * The settings presenter may replace the item list shortly after the first layout, so re-check the
     * row once the initial data/animations have settled.
     */
    private static void verifyLater(final Activity activity, long delayMs) {
        try {
            activity.getWindow().getDecorView().postDelayed(new Runnable() {
                @Override
                public void run() {
                    try {
                        attach(activity, false);
                    } catch (Throwable ignored) {
                    }
                }
            }, delayMs);
        } catch (Throwable ignored) {
        }
    }

    /** Re-insert the row after the settings list is rebuilt; safe to call repeatedly. */
    public static void ensure(final Activity activity) {
        try {
            if (activity != null) {
                schedule(activity, 0);
            }
        } catch (Throwable ignored) {
        }
    }

    private static void schedule(final Activity activity, final int attempt) {
        try {
            activity.getWindow().getDecorView().postDelayed(new Runnable() {
                @Override
                public void run() {
                    boolean done = false;
                    try {
                        done = attach(activity, attempt >= MAX_ATTEMPTS);
                    } catch (Throwable ignored) {
                    }
                    if (!done && attempt < MAX_ATTEMPTS) {
                        schedule(activity, attempt + 1);
                    }
                }
            }, attempt == 0 ? 0L : RETRY_DELAY_MS);
        } catch (Throwable ignored) {
        }
    }

    private static boolean attach(Activity activity, boolean allowFallback) {
        View content = activity.findViewById(android.R.id.content);
        Object adapter = findAdapter(content);
        if (adapter == null) {
            return false;
        }
        Object binder = newBinder();
        if (binder == null || !register(adapter, binder)) {
            return false;
        }
        return insertRow(adapter, activity, allowFallback);
    }

    private static Object findAdapter(View view) {
        if (view == null) {
            return null;
        }
        if (RECYCLER_CLASS.equals(view.getClass().getName())) {
            Object adapter = invoke(view, "getAdapter");
            if (adapter != null && isMultiTypeAdapter(adapter)) {
                return adapter;
            }
        }
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            int count = group.getChildCount();
            for (int index = 0; index < count; index++) {
                Object found = findAdapter(group.getChildAt(index));
                if (found != null) {
                    return found;
                }
            }
        }
        return null;
    }

    /** The settings adapter may be an app subclass, so accept anything derived from the base. */
    private static boolean isMultiTypeAdapter(Object adapter) {
        try {
            return Class.forName(ADAPTER_CLASS).isInstance(adapter);
        } catch (Throwable ignored) {
            return ADAPTER_CLASS.equals(adapter.getClass().getName());
        }
    }

    private static Object newBinder() {
        try {
            return Class.forName(BINDER_CLASS).getDeclaredConstructor().newInstance();
        } catch (Throwable ignored) {
            return null;
        }
    }

    private static boolean register(Object adapter, Object binder) {
        synchronized (REGISTERED) {
            if (REGISTERED.containsKey(adapter)) {
                return true;
            }
        }
        try {
            Method[] methods = adapter.getClass().getMethods();
            for (int index = 0; index < methods.length; index++) {
                Method method = methods[index];
                Class<?>[] types = method.getParameterTypes();
                if (types.length != 2 || types[0] != Class.class) {
                    continue;
                }
                if (method.getReturnType() != Void.TYPE
                        || !types[1].isAssignableFrom(binder.getClass())) {
                    continue;
                }
                method.invoke(adapter, BlockEntry.class, binder);
                synchronized (REGISTERED) {
                    REGISTERED.put(adapter, Boolean.TRUE);
                }
                return true;
            }
        } catch (Throwable ignored) {
        }
        return false;
    }

    private static boolean insertRow(Object adapter, Activity activity, boolean allowFallback) {
        try {
            List<?> items = items(adapter);
            if (items == null) {
                return false;
            }
            for (int index = 0; index < items.size(); index++) {
                if (items.get(index) instanceof BlockEntry) {
                    return true;
                }
            }
            String title = aboutTitle(activity);
            int position = -1;
            for (int index = 0; index < items.size(); index++) {
                if (containsText(items.get(index), title, 2)) {
                    position = index;
                }
            }
            if (position < 0) {
                if (!allowFallback) {
                    return false;
                }
                position = items.size() - 1;
            }
            ArrayList<Object> updated = new ArrayList<Object>(items);
            updated.add(position + 1, new BlockEntry());
            return replaceItems(adapter, updated);
        } catch (Throwable ignored) {
        }
        return false;
    }

    private static List<?> items(Object adapter) {
        try {
            Method[] methods = adapter.getClass().getMethods();
            for (int index = 0; index < methods.length; index++) {
                Method method = methods[index];
                if (method.getParameterTypes().length != 0) {
                    continue;
                }
                if (!List.class.isAssignableFrom(method.getReturnType())) {
                    continue;
                }
                Object value = method.invoke(adapter);
                if (value instanceof List) {
                    return (List<?>) value;
                }
            }
        } catch (Throwable ignored) {
        }
        return null;
    }

    private static boolean replaceItems(Object adapter, List<Object> updated) {
        try {
            Method[] methods = adapter.getClass().getMethods();
            for (int index = 0; index < methods.length; index++) {
                Method method = methods[index];
                Class<?>[] types = method.getParameterTypes();
                if (types.length == 1 && types[0] == List.class
                        && method.getReturnType() == Void.TYPE) {
                    method.invoke(adapter, updated);
                    notifyChanged(adapter);
                    return true;
                }
            }
        } catch (Throwable ignored) {
        }
        return false;
    }

    /** The obfuscated item setter only swaps the backing list, so refresh the list explicitly. */
    private static void notifyChanged(Object adapter) {
        try {
            Method method = adapter.getClass().getMethod("notifyDataSetChanged");
            method.invoke(adapter);
        } catch (Throwable ignored) {
        }
    }

    private static String aboutTitle(Activity activity) {
        try {
            int id = activity.getResources().getIdentifier(
                    "setting_about", "string", activity.getPackageName());
            if (id != 0) {
                String value = activity.getString(id);
                if (value != null && value.length() > 0) {
                    return value;
                }
            }
        } catch (Throwable ignored) {
        }
        return ABOUT_TITLE;
    }

    private static boolean containsText(Object item, String title, int depth) {
        if (item == null || title == null) {
            return false;
        }
        if (item instanceof String) {
            return title.equals(((String) item).trim());
        }
        if (depth <= 0) {
            return false;
        }
        Class<?> type = item.getClass();
        for (int level = 0; level < 3 && type != null && type != Object.class; level++) {
            Field[] fields;
            try {
                fields = type.getDeclaredFields();
            } catch (Throwable ignored) {
                break;
            }
            for (int index = 0; index < fields.length; index++) {
                Field field = fields[index];
                try {
                    if (field.getType() == String.class) {
                        field.setAccessible(true);
                        Object value = field.get(item);
                        if (value instanceof String && title.equals(((String) value).trim())) {
                            return true;
                        }
                    } else if (!field.getType().isPrimitive()) {
                        field.setAccessible(true);
                        Object value = field.get(item);
                        if (value != null && value != item && containsText(value, title, depth - 1)) {
                            return true;
                        }
                    }
                } catch (Throwable ignored) {
                }
            }
            type = type.getSuperclass();
        }
        return false;
    }

    private static Object invoke(Object target, String name) {
        try {
            Method method = target.getClass().getMethod(name);
            return method.invoke(target);
        } catch (Throwable ignored) {
            return null;
        }
    }
}
""",
}


def settings_smali_target(decoded_dir: Path) -> Path:
    """Return the smali directory of the dex that holds the settings activity."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_rednote import dex_name_for_smali, find_smali_class

    smali = find_smali_class(decoded_dir, SETTINGS_ACTIVITY)
    dex_entry = dex_name_for_smali(decoded_dir, smali)
    marker = f"/smali/{dex_entry[:-4]}/"
    resolved = smali.resolve().as_posix()
    if marker not in resolved:
        raise ValueError(f"Unexpected smali layout for {smali}")
    root = Path(resolved.split(marker)[0]) / "smali" / dex_entry[:-4]
    return root


def declare_block_words_activity(manifest_root) -> dict:
    """Add the keyword-settings activity element to the decoded manifest."""
    import xml.etree.ElementTree as ET

    application = next(
        (child for child in list(manifest_root) if child.tag.split("}")[-1] == "application"),
        None,
    )
    if application is None:
        raise ValueError("Manifest application element is missing")
    for child in list(application):
        name = child.get(f"{{{ANDROID_NS}}}name")
        if child.tag.split("}")[-1] in {"activity", "activity-alias"} and name == ACTIVITY_CLASS:
            raise ValueError("Block-words activity is already declared in the manifest")
    activity = ET.SubElement(application, "activity")
    activity.set(f"{{{ANDROID_NS}}}name", ACTIVITY_CLASS)
    activity.set(f"{{{ANDROID_NS}}}exported", "false")
    activity.set(f"{{{ANDROID_NS}}}theme", "@android:style/Theme.Material.Light.DarkActionBar")
    activity.set(
        f"{{{ANDROID_NS}}}configChanges",
        "orientation|screenSize|keyboardHidden|uiMode",
    )
    return {
        "activity": ACTIVITY_CLASS,
        "exported": False,
        "theme": "@android:style/Theme.Material.Light.DarkActionBar",
    }


def patch_settings_activity(smali_path: Path) -> dict:
    text = smali_path.read_text()
    pattern = r"^\.method public onCreate\(Landroid/os/Bundle;\)V\n.*?^\.end method"
    methods = list(re.finditer(pattern, text, re.M | re.S))
    if len(methods) != 1:
        raise ValueError("Expected exactly one settings activity onCreate method")
    match = methods[0]
    original = match.group()
    if hashlib.sha256(original.encode()).hexdigest() != EXPECTED_ONCREATE_SHA:
        raise ValueError("Settings activity onCreate differs from the verified REDnote input")
    if original.count(SETTINGS_ACTIVITY_LAUNCH) != 1:
        raise ValueError("Unexpected settings activity onCreate layout")
    patched = original.replace(SETTINGS_ACTIVITY_LAUNCH, SETTINGS_ACTIVITY_LAUNCH + SETTINGS_ACTIVITY_HOOK, 1)
    text = text[: match.start()] + patched + text[match.end():]

    focus = list(re.finditer(r"^\.method public onWindowFocusChanged\(Z\)V\n.*?^\.end method", text, re.M | re.S))
    if len(focus) != 1:
        raise ValueError("Expected exactly one settings activity onWindowFocusChanged method")
    focus_match = focus[0]
    focus_original = focus_match.group()
    if hashlib.sha256(focus_original.encode()).hexdigest() != EXPECTED_FOCUS_SHA:
        raise ValueError("Settings activity onWindowFocusChanged differs from the verified REDnote input")
    if focus_original.count(FOCUS_SUPER_CALL) != 1:
        raise ValueError("Unexpected settings activity onWindowFocusChanged layout")
    focus_patched = focus_original.replace(
        FOCUS_SUPER_CALL, FOCUS_SUPER_CALL + FOCUS_ENSURE_HOOK, 1
    )
    smali_path.write_text(
        text[: focus_match.start()] + focus_patched + text[focus_match.end():]
    )
    return {
        "class": SETTINGS_ACTIVITY,
        "method": "onCreate(Landroid/os/Bundle;)V",
        "originalMethodSha256": EXPECTED_ONCREATE_SHA,
        "refreshMethod": "onWindowFocusChanged(Z)V",
        "refreshMethodSha256": EXPECTED_FOCUS_SHA,
        "hookClass": "dev.kiri.xhsads.SettingsHook",
    }


def patch_feed_keyword_filter(smali_path: Path) -> dict:
    """Extend the ad-display feed hook with the keyword check (call after --hide-feed-ads)."""
    text = smali_path.read_text()
    if "rednote_feed_keyword_done" in text:
        raise ValueError("Feed keyword filter hook is already present")
    if text.count(FEED_APPLY_BLOCK) != 1:
        raise ValueError("Expected exactly one compiled feed display hook to extend")
    patched = text.replace(FEED_APPLY_BLOCK, FEED_APPLY_BLOCK_KEYWORDS, 1)
    if "if-eqz v1, :rednote_feed_keyword_done" in patched:
        raise ValueError("Keyword filter must be skipped for ads, not for regular cards")
    smali_path.write_text(patched)
    return {
        "hookPoint": "FeedCustomMultiTypeAdapter.onBindViewHolder (post-bind display hook)",
        "keywordCall": "Ldev/kiri/xhsads/FeedKeywordFilter;->matches(Landroid/view/View;Ljava/lang/Object;)Z",
        "sameDisplayStateAsAdPatch": True,
    }


def write_helper_smali(decoded_dir: Path) -> list[Path]:
    """Write the obfuscated-interface binder classes into the settings dex smali tree."""
    root = settings_smali_target(decoded_dir) / HELPER_PACKAGE
    root.mkdir(parents=True, exist_ok=True)
    written = []
    for name, body in SMALI_CLASSES.items():
        path = root / name
        path.write_text(body)
        written.append(path)
    return written


def build_block_words_dex(work_dir: Path) -> Path:
    """Compile the keyword/settings helper classes into a min-api-21 classes.dex."""
    work_dir = Path(work_dir)
    root = work_dir / "block-words-helper"
    if root.exists():
        shutil.rmtree(root)

    source_root = root / "src"
    classes_dir = root / "classes"
    dex_dir = root / "dex"
    classes_dir.mkdir(parents=True)
    dex_dir.mkdir(parents=True)

    package_dir = source_root / HELPER_PACKAGE
    package_dir.mkdir(parents=True)
    files = []
    for name, body in JAVA_SOURCES.items():
        path = package_dir / name
        path.write_text(body, encoding="utf-8", newline="\n")
        files.append(path)

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
        *files,
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
        raise RuntimeError("Java compiler did not produce block-words helper classes")

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
        raise RuntimeError("D8 did not produce the block-words helper classes.dex")
    return dex


def verify_compiled_settings_hook(apk: Path, settings_dex: str) -> dict:
    """Assert the compiled settings dex carries the hook and the binder classes."""
    import struct
    import sys
    import zipfile

    sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
    from verify_rednote_signature_compat import DexFile

    with zipfile.ZipFile(apk) as archive:
        dex = DexFile(archive.read(settings_dex), settings_dex)

    for descriptor in (
        "Ldev/kiri/xhsads/BlockBinder;",
        "Ldev/kiri/xhsads/BlockViewHolder;",
    ):
        if len(dex.class_definitions(descriptor)) != 1:
            raise ValueError(f"{settings_dex} is missing helper class {descriptor}")

    binder = dex.class_definitions("Ldev/kiri/xhsads/BlockBinder;")[0]
    if _superclass_descriptor(dex, binder["descriptor"]) != BINDER_BASE:
        raise ValueError("BlockBinder does not extend the verified MultiType binder base")

    definitions = dex.class_definitions(SETTINGS_ACTIVITY_DESCRIPTOR)
    if len(definitions) != 1:
        raise ValueError(f"{settings_dex} is missing the settings activity")
    records = dex.method_records(definitions[0])
    codes = [
        code
        for index, _, code in records
        if dex.method_id(index) == (SETTINGS_ACTIVITY_DESCRIPTOR, "onCreate", "(Landroid/os/Bundle;)V")
    ]
    if len(codes) != 1:
        raise ValueError("Expected one compiled settings activity onCreate")
    target = ("Ldev/kiri/xhsads/SettingsHook;", "install", "(Landroid/app/Activity;)V")
    if not _method_calls(dex, codes[0], target):
        raise ValueError("Compiled settings activity onCreate does not call SettingsHook.install")
    focus_codes = [
        code
        for index, _, code in records
        if dex.method_id(index) == (SETTINGS_ACTIVITY_DESCRIPTOR, "onWindowFocusChanged", "(Z)V")
    ]
    if len(focus_codes) != 1:
        raise ValueError("Expected one compiled settings activity onWindowFocusChanged")
    refresh = ("Ldev/kiri/xhsads/SettingsHook;", "ensure", "(Landroid/app/Activity;)V")
    if not _method_calls(dex, focus_codes[0], refresh):
        raise ValueError("Compiled settings activity does not refresh the entry on focus")
    return {
        "verified": True,
        "dex": settings_dex,
        "entryHook": True,
        "refreshHook": True,
        "binderClass": "Ldev/kiri/xhsads/BlockBinder;",
        "binderBase": BINDER_BASE,
    }


def verify_compiled_feed_keyword_hook(apk: Path) -> dict:
    """Assert the compiled feed bind hook calls the keyword filter before applying state."""
    import struct
    import sys
    import zipfile

    sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
    from verify_rednote_signature_compat import DexFile

    adapter = "com.xingin.xhs.homepage.explorefeed.mainfeed.view.FeedCustomMultiTypeAdapter"
    descriptor = "L" + adapter.replace(".", "/") + ";"
    proto = "(Landroidx/recyclerview/widget/RecyclerView$ViewHolder;ILjava/util/List;)V"
    with zipfile.ZipFile(apk) as archive:
        dex = DexFile(archive.read("classes19.dex"), "classes19.dex")
    definitions = dex.class_definitions(descriptor)
    if len(definitions) != 1:
        raise ValueError("Expected one feed adapter in classes19.dex")
    codes = [
        code
        for index, _, code in dex.method_records(definitions[0])
        if dex.method_id(index) == (descriptor, "onBindViewHolder", proto)
    ]
    if len(codes) != 1:
        raise ValueError("Expected one compiled feed bind method")
    keyword_call = ("Ldev/kiri/xhsads/FeedKeywordFilter;", "matches",
                    "(Landroid/view/View;Ljava/lang/Object;)Z")
    apply_call = ("Ldev/kiri/xhsads/FeedAdDisplay;", "apply", "(Landroid/view/View;Z)V")
    calls = _ordered_calls(dex, codes[0])
    keyword_positions = [position for position, method in calls if method == keyword_call]
    apply_positions = [position for position, method in calls if method == apply_call]
    if len(keyword_positions) != 1 or len(apply_positions) != 2:
        raise ValueError("Compiled feed hook must call the keyword filter once and apply twice")
    if not keyword_positions[0] < apply_positions[-1]:
        raise ValueError("Compiled feed hook calls the keyword filter after the display apply")
    return {
        "verified": True,
        "dex": "classes19.dex",
        "keywordFilterCall": True,
        "keywordCheckedBeforeApply": True,
    }


def _superclass_descriptor(dex, descriptor: str) -> str | None:
    """Read the superclass type of a defined class straight from its class_def item."""
    for index in range(dex.class_count):
        offset = dex.class_off + index * 32
        if dex.type_descriptor(dex.u32(offset)) != descriptor:
            continue
        superclass_idx = dex.u32(offset + 8)
        if superclass_idx == 0xFFFFFFFF:
            return None
        return dex.type_descriptor(superclass_idx)
    return None


def _ordered_calls(dex, code: int) -> list[tuple[int, tuple[str, str, str]]]:
    import struct

    _, count = dex.code_info(code)
    units = list(struct.unpack_from("<" + "H" * count, dex.data, code + 16))
    calls: list[tuple[int, tuple[str, str, str]]] = []
    position = 0
    while position < len(units):
        opcode = units[position] & 0xFF
        if 0x6E <= opcode <= 0x72 or 0x74 <= opcode <= 0x78:
            calls.append((position, dex.method_id(units[position + 1])))
        position += dex._instruction_width(units, position)
    return calls


def _method_calls(dex, code: int, target: tuple[str, str, str]) -> bool:
    return any(method == target for _, method in _ordered_calls(dex, code))
