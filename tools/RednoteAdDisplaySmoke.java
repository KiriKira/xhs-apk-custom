package dev.kiri.xhsads.smoke;

import android.content.Context;
import android.os.Looper;
import android.view.View;
import android.view.ViewGroup;

import dalvik.system.PathClassLoader;

import java.io.File;
import java.lang.reflect.Method;

/** Run with app_process on Android, passing the APK containing FeedAdDisplay. */
public final class RednoteAdDisplaySmoke {
    private RednoteAdDisplaySmoke() {
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 1 || !new File(args[0]).isFile()) {
            throw new IllegalArgumentException("Expected one readable APK path");
        }
        if (Looper.myLooper() == null) {
            Looper.prepare();
        }

        Context context = systemContext();
        ClassLoader apkLoader = new PathClassLoader(args[0], ClassLoader.getSystemClassLoader());
        Class<?> helper = Class.forName("dev.kiri.xhsads.FeedAdDisplay", true, apkLoader);
        Method apply = helper.getMethod("apply", View.class, boolean.class);

        View recycled = new View(context);
        recycled.setLayoutParams(new ViewGroup.LayoutParams(100, 240));
        apply.invoke(null, recycled, true);
        boolean hidden = recycled.getVisibility() == View.GONE
                && recycled.getLayoutParams().height == 0;
        apply.invoke(null, recycled, true);
        boolean repeatedHideStable = recycled.getVisibility() == View.GONE
                && recycled.getLayoutParams().height == 0;
        apply.invoke(null, recycled, false);
        boolean restored = recycled.getVisibility() == View.VISIBLE
                && recycled.getLayoutParams().height == 240;

        // Restore before a new bind; the next note may have a different height.
        apply.invoke(null, recycled, true);
        apply.invoke(null, recycled, false);
        recycled.getLayoutParams().height = 420;
        apply.invoke(null, recycled, false);
        boolean newBindHeightPreserved = recycled.getVisibility() == View.VISIBLE
                && recycled.getLayoutParams().height == 420;

        View wrapContent = new View(context);
        wrapContent.setLayoutParams(new ViewGroup.LayoutParams(100, ViewGroup.LayoutParams.WRAP_CONTENT));
        apply.invoke(null, wrapContent, true);
        apply.invoke(null, wrapContent, false);
        boolean wrapContentRestored = wrapContent.getLayoutParams().height == ViewGroup.LayoutParams.WRAP_CONTENT;

        View ordinaryGone = new View(context);
        ordinaryGone.setLayoutParams(new ViewGroup.LayoutParams(100, 240));
        ordinaryGone.setVisibility(View.GONE);
        apply.invoke(null, ordinaryGone, false);
        boolean ordinaryGoneUnchanged = ordinaryGone.getVisibility() == View.GONE
                && ordinaryGone.getLayoutParams().height == 240;

        View withoutParams = new View(context);
        apply.invoke(null, withoutParams, true);
        apply.invoke(null, withoutParams, false);
        boolean nullLayoutParamsSafe = withoutParams.getVisibility() == View.VISIBLE
                && withoutParams.getLayoutParams() == null;
        apply.invoke(null, (Object) null, true);
        apply.invoke(null, (Object) null, false);

        boolean[] checks = new boolean[] {
                hidden,
                repeatedHideStable,
                restored,
                ordinaryGoneUnchanged,
                nullLayoutParamsSafe,
                newBindHeightPreserved,
                wrapContentRestored,
                true
        };
        String[] names = new String[] {
                "ad_hidden",
                "repeated_hide_stable",
                "ordinary_restored",
                "ordinary_gone_unchanged",
                "null_layout_params_safe",
                "new_bind_height_preserved",
                "wrap_content_restored",
                "null_view_safe"
        };
        StringBuilder json = new StringBuilder("{\"checks\":{");
        for (int i = 0; i < checks.length; i++) {
            if (i != 0) {
                json.append(',');
            }
            json.append('"').append(names[i]).append("\":").append(checks[i]);
        }
        json.append("}}\n");
        System.out.print(json.toString());

        for (boolean passed : checks) {
            if (!passed) {
                throw new AssertionError("Android ad display smoke check failed");
            }
        }
    }

    private static Context systemContext() throws Exception {
        Class<?> activityThread = Class.forName("android.app.ActivityThread");
        Method systemMain = activityThread.getDeclaredMethod("systemMain");
        systemMain.setAccessible(true);
        Object thread = systemMain.invoke(null);
        Method getSystemContext = activityThread.getDeclaredMethod("getSystemContext");
        getSystemContext.setAccessible(true);
        return (Context) getSystemContext.invoke(thread);
    }
}
