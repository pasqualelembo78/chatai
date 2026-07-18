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

# Remove debug logs in release
-assumenosideeffects class android.util.Log {
    public static boolean isLoggable(java.lang.String, int);
    public static int v(...);
    public static int d(...);
    public static int i(...);
}

# Keep AuthManager (token storage / network layer)
-keep class com.intelligame.chatai.AuthManager { *; }

# Keep Parcelable implementations (avoid missing CREATOR after obfuscation)
-keep class * implements android.os.Parcelable {
    public static final android.os.Parcelable$Creator *;
}

# Keep Application subclass and manifest-registered components by name
-keep public class com.intelligame.chatai.ChatApplication
-keep public class * extends android.app.Activity
-keep public class * extends android.app.Service
-keep public class * extends android.content.BroadcastReceiver
-keep public class * extends androidx.fragment.app.Fragment
