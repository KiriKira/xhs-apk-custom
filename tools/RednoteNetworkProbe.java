import java.net.HttpURLConnection;
import java.net.URL;

/** Account-free guest connectivity check using Android's normal TLS trust. */
public final class RednoteNetworkProbe {
    public static void main(String[] args) {
        String[] urls = {"https://www.google.com/generate_204",
                         "https://www.rednote.com/",
                         "https://edith.xiaohongshu.com/"};
        for (String value : urls) {
            HttpURLConnection connection = null;
            long started = System.nanoTime();
            String host = "";
            try {
                URL url = new URL(value);
                host = url.getHost();
                connection = (HttpURLConnection) url.openConnection();
                connection.setConnectTimeout(10000);
                connection.setReadTimeout(10000);
                connection.setInstanceFollowRedirects(false);
                connection.setRequestProperty("User-Agent", "Android-VM-connectivity-test");
                int code = connection.getResponseCode();
                System.out.println("network_probe host=" + host + " http_status=" + code
                        + " elapsed_ms=" + ((System.nanoTime() - started) / 1000000));
            } catch (Exception failure) {
                System.out.println("network_probe host=" + host + " error="
                        + failure.getClass().getSimpleName() + " elapsed_ms="
                        + ((System.nanoTime() - started) / 1000000));
            } finally {
                if (connection != null) connection.disconnect();
            }
        }
    }
}
