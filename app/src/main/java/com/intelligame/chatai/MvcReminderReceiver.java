package com.intelligame.chatai;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

import androidx.core.app.NotificationCompat;

public class MvcReminderReceiver extends BroadcastReceiver {

    public static final String CHANNEL_ID = "mvc_reminders";
    public static final int NOTIFICATION_ID = 30511;

    @Override
    public void onReceive(Context context, Intent intent) {
        NotificationManager nm =
                (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null) return;

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel ch = new NotificationChannel(
                    CHANNEL_ID, "Promemoria MevaCoin",
                    NotificationManager.IMPORTANCE_DEFAULT);
            ch.setDescription("Promemoria per le missioni MVC giornaliere");
            nm.createNotificationChannel(ch);
        }

        Intent open = new Intent(context, MainActivity.class);
        open.putExtra("open_earn", true);
        open.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent pi = PendingIntent.getActivity(context, 0, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        NotificationCompat.Builder b = new NotificationCompat.Builder(context, CHANNEL_ID)
                .setSmallIcon(R.mipmap.ic_launcher)
                .setContentTitle("Nuove missioni MVC!")
                .setContentText("Apri l'app e guadagna MevaCoin con le missioni di oggi.")
                .setContentIntent(pi)
                .setAutoCancel(true)
                .setPriority(NotificationCompat.PRIORITY_DEFAULT);

        nm.notify(NOTIFICATION_ID, b.build());
    }
}
