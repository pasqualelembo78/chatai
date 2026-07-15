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

# Keep Glide
-keep public class * implements com.bumptech.glide.module.GlideModule
-keep class * extends com.bumptech.glide.module.AppGlideModule { <init>(...); }
-keep public enum com.bumptech.glide.load.ImageHeaderParser$** {
  **[] $VALUES;
  public *;
}
-keep public class * extends com.bumptech.glide.GeneratedAppGlideModule
-dontwarn com.bumptech.glide.**

# Keep ChatViewerFragment (used via fragment navigation)
-keep class com.intelligame.chatadmin.ChatViewerFragment { *; }

# Remove debug logs in release
-assumenosideeffects class android.util.Log {
    public static boolean isLoggable(java.lang.String, int);
    public static int v(...);
    public static int d(...);
    public static int i(...);
}

# Keep Tink crypto (used by security-crypto)
-keep class com.google.crypto.tink.** { *; }
-dontwarn com.google.crypto.tink.**

# Ignore missing javax.annotation classes (Tink references)
-dontwarn javax.annotation.**
-dontwarn javax.annotation.concurrent.**
-dontwarn org.checkerframework.**
