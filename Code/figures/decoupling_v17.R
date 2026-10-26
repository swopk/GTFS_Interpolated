# Figure 3: share of stop times flagged approximate against sub-minute precision.
graphics.off()

d <- read.csv("../../data_files/feed_data_v2.csv")
out_dir <- ""

dec <- d[d$timepoint_status == "declared", ]
valid_mask <- complete.cases(dec$share_stop_times_whole_minute, dec$approximate_share)
dec_clean <- dec[valid_mask, ]

x <- 100 * (1 - dec_clean$share_stop_times_whole_minute)
y <- 100 * dec_clean$approximate_share

r_val <- cor(x, y, use = "complete.obs")
n_zero <- sum(x == 0)
n_diag <- sum(abs(x - y) <= 5 & x > 0)
cat(n_zero, "feeds in the vertical band,", n_diag, "feeds within 5 points of the diagonal\n")

y_hist <- hist(y, breaks = seq(0, 100, length.out = 31), plot = FALSE)
pct_axis <- seq(0, 100, by = 20)

draw_combined_figure <- function() {
  layout(matrix(c(1, 2), nrow = 1, ncol = 2), widths = c(1.1, 4))

  par(mar = c(3.0, 1.8, 0.8, 0.0), family = "sans", mgp = c(1.6, 0.5, 0))
  h_max <- max(100, 10 * ceiling(max(y_hist$counts) / 10))
  barplot(y_hist$counts,
          horiz = TRUE,
          space = 0,
          col = "#B9CBE4",
          border = "#3B629B",
          lwd = 0.6,
          ylim = c(0, length(y_hist$counts)),
          xlim = c(h_max, 0),
          axes = FALSE,
          xlab = "")
  axis(1, at = c(0, 50, 100), cex.axis = 0.75, col.axis = "#374151", padj = -0.5)
  title(xlab = "Feeds", line = 1.6, font.lab = 3, cex.lab = 0.85, col.lab = "#1F2937")

  par(mar = c(3.0, 3.4, 0.8, 0.6), family = "sans", mgp = c(2.2, 0.4, 0))
  plot(x, y,
       type = "n",
       axes = FALSE,
       xlab = "",
       ylab = "Share of stop times flagged approximate",
       cex.lab = 0.90,
       font.lab = 3,
       col.lab = "#1F2937",
       xlim = c(0, 100),
       ylim = c(0, 100))
  abline(h = pct_axis, v = pct_axis, col = "#E2E8F0", lwd = 0.7)
  abline(0, 1, lty = 2, col = "#6B7280", lwd = 0.8)
  box(col = "#374151")
  axis(1, at = pct_axis, labels = paste0(pct_axis, "%"), cex.axis = 0.85, col.axis = "#374151")
  axis(2, at = pct_axis, labels = paste0(pct_axis, "%"), las = 1, cex.axis = 0.85, col.axis = "#374151")
  points(x, y, pch = 16, cex = 0.55, col = adjustcolor("#3B629B", alpha.f = 0.30))
  title(xlab = "Sub-minute precision (share of stop times not on a whole minute)",
        line = 1.8, font.lab = 3, cex.lab = 0.90, col.lab = "#1F2937")

  legend("bottomright",
         inset = c(0.04, 0.04),
         legend = c(paste0("n = ", format(length(x), big.mark = ",")),
                    as.expression(bquote(italic(r) == .(sprintf("%.2f", r_val))))),
         bty = "n",
         cex = 0.82,
         text.col = "#1F2937")
}

pdf(paste0(out_dir, "decoupling_v17.pdf"), width = 7.5, height = 5.2)
draw_combined_figure()
dev.off()

jpeg(paste0(out_dir, "decoupling_v17.jpeg"), width = 2250, height = 1560, res = 300, quality = 100)
draw_combined_figure()
dev.off()

if (interactive()) {
  dev.new(width = 7.5, height = 5.2, noRStudioGD = TRUE)
  draw_combined_figure()
}
