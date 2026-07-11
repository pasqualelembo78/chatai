package com.intelligame.chatai;

import android.content.Context;
import android.graphics.drawable.Drawable;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;

import androidx.annotation.NonNull;
import androidx.core.content.ContextCompat;
import androidx.recyclerview.widget.RecyclerView;

import com.google.android.material.button.MaterialButton;

import java.util.List;

public class CategoryAdapter extends RecyclerView.Adapter<CategoryAdapter.ViewHolder> {

    private final List<HomeFragment.Category> categories;
    private final OnCategoryClickListener listener;
    private int selectedPosition = 0;

    public interface OnCategoryClickListener {
        void onCategoryClick(HomeFragment.Category category);
    }

    public CategoryAdapter(List<HomeFragment.Category> categories, OnCategoryClickListener listener) {
        this.categories = categories;
        this.listener = listener;
    }

    public void setSelected(int position) {
        int oldPos = selectedPosition;
        selectedPosition = position;
        notifyItemChanged(oldPos);
        notifyItemChanged(position);
    }

    @NonNull
    @Override
    public ViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View view = LayoutInflater.from(parent.getContext())
            .inflate(R.layout.item_category_chip, parent, false);
        return new ViewHolder(view);
    }

    @Override
    public void onBindViewHolder(@NonNull ViewHolder holder, int position) {
        HomeFragment.Category category = categories.get(position);
        MaterialButton button = holder.button;
        Context context = button.getContext();

        // Prova a caricare l'icona PNG personalizzata
        Drawable iconDrawable = null;
        int iconResId = context.getResources().getIdentifier(
            "cat_" + category.id, "drawable", context.getPackageName());
        if (iconResId != 0) {
            iconDrawable = ContextCompat.getDrawable(context, iconResId);
        }

        String label = category.name;
        if (category.locked) {
            label = "\uD83D\uDD12 " + label + " (" + category.mvcCost + " MVC)";
        }
        button.setText(label);

        // Imposta l'icona PNG se disponibile, altrimenti usa l'emoji
        if (iconDrawable != null) {
            button.setIcon(iconDrawable);
            button.setIconTint(null);
            button.setIconSize((int) (18 * context.getResources().getDisplayMetrics().density));
        } else {
            // Fallback all'emoji nel testo
            button.setText(category.icon + " " + label);
            button.setIcon(null);
        }

        boolean isSelected = position == selectedPosition;
        button.setChecked(isSelected);
        if (isSelected) {
            button.setBackgroundColor(context.getColor(R.color.category_chip_selected));
        } else if (category.locked) {
            button.setBackgroundColor(context.getColor(R.color.surface_container));
        } else {
            button.setBackgroundColor(context.getColor(R.color.category_chip_bg));
        }

        button.setOnClickListener(v -> {
            if (position != selectedPosition) {
                setSelected(position);
                listener.onCategoryClick(category);
            }
        });
    }

    @Override
    public int getItemCount() {
        return categories.size();
    }

    static class ViewHolder extends RecyclerView.ViewHolder {
        final MaterialButton button;

        ViewHolder(View itemView) {
            super(itemView);
            button = itemView.findViewById(R.id.chip_button);
        }
    }
}
