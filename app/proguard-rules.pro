# Keep socket.io client
-keep class io.socket.** { *; }
-dontwarn io.socket.**

# Keep Google Sign-In
-keep class com.google.android.gms.auth.** { *; }
-keep class com.google.android.gms.common.** { *; }
-dontwarn com.google.android.gms.**

# Keep EncryptedSharedPreferences
-keep class androidx.security.crypto.** { *; }
-dontwarn androidx.security.crypto.**

# Keep JSON (Android built-in)
-keep class org.json.** { *; }

# Keep WebView JS interface (se usato)
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}

# Remove debug logs in release
-assumenosideeffects class android.util.Log {
    public static boolean isLoggable(java.lang.String, int);
    public static int v(...);
    public static int d(...);
    public static int i(...);
}
