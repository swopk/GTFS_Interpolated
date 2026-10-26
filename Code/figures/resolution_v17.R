# Figure 2: distribution of the share of inter-stop travel times on a whole minute.
graphics.off()

d <- read.csv("../../data_files/feed_data_v2.csv")
out_dir <- ""

brk <- seq(0, 1, by = 0.05)
d$bin <- cut(d$share_travel_times_whole_minute, breaks = brk,
             include.lowest = TRUE, right = FALSE)
d$tp <- factor(d$timepoint_status, levels = c("declared", "not_declared"))

counts <- table(d$tp, d$bin)
totals <- colSums(counts)
n_all <- nrow(d)
mid <- 2:(length(totals) - 1)
n_mid <- sum(totals[mid])
tp_mid <- sum(counts["declared", mid]) / n_mid

pct <- function(x) paste0(round(100 * x), "%")
lab_low <- paste0("Written to the second\nn = ", format(totals[1], big.mark = ","), " (",
                  pct(totals[1] / n_all), "), fewer than 5%")
lab_high <- paste0("Whole-minute feeds\nn = ", format(totals[length(totals)], big.mark = ","), " (",
                   pct(totals[length(totals)] / n_all), "), at least 95%")
lab_mid <- bquote("Mixed: n = " * .(n_mid) * " (" * .(pct(n_mid / n_all)) * "), " *
                    .(pct(tp_mid)) * " populate " * italic("timepoint"))

cols <- c("#3B629B", "#C86D7C")

draw_resolution_plot <- function() {
  par(mar = c(3.4, 4.4, 0.8, 0.6), family = "sans", mgp = c(3.0, 0.5, 0))

  yt <- pretty(c(0, max(totals)))
  bp <- barplot(counts, col = cols, border = "#4A5568", lwd = 0.6, space = 0.15,
                ylim = c(0, max(totals) * 1.15), names.arg = rep("", length(totals)),
                axes = FALSE, ylab = "Number of feeds", cex.lab = 0.90, font.lab = 3,
                col.lab = "#1F2937")
  abline(h = yt, col = "#E2E8F0", lwd = 0.7)
  barplot(counts, col = cols, border = "#4A5568", lwd = 0.6, space = 0.15,
          names.arg = rep("", length(totals)), add = TRUE, axes = FALSE)
  axis(2, at = yt, labels = format(yt, big.mark = ",", trim = TRUE), las = 1,
       cex.axis = 0.85, col.axis = "#374151")

  edges <- c(bp - diff(bp)[1] / 2, bp[length(bp)] + diff(bp)[1] / 2)
  at <- edges[c(1, 6, 11, 16, 21)]
  axis(1, at = at, labels = c("0%", "25%", "50%", "75%", "100%"),
       cex.axis = 0.85, col.axis = "#374151")
  title(xlab = "Share of a feed's inter-stop travel times on a whole minute",
        line = 2.0, font.lab = 3, cex.lab = 0.90, col.lab = "#1F2937")

  gap <- max(totals) * 0.025
  text(edges[1], totals[1] + gap, lab_low, adj = c(0, 0), cex = 0.75, font = 2, col = "#1E293B")
  text(edges[length(edges)], totals[length(totals)] + gap, lab_high, adj = c(1, 0),
       cex = 0.75, font = 2, col = "#1E293B")

  ymid <- max(totals[mid]) + max(totals) * 0.06
  x0 <- edges[min(mid)]
  x1 <- edges[max(mid) + 1]
  segments(x0, ymid, x1, ymid, col = "#4B5563", lwd = 0.8)
  segments(c(x0, x1), ymid, c(x0, x1), ymid - gap, col = "#4B5563", lwd = 0.8)
  text((x0 + x1) / 2, ymid + gap * 0.6, lab_mid, adj = c(0.5, 0), cex = 0.75, col = "#1E293B")

  legend(x = edges[10], y = 900, xjust = 0.5, yjust = 0.5,
         legend = c(expression(italic("timepoint") * " populated"),
                    expression(italic("timepoint") * " not populated")),
         fill = cols, border = "#4A5568", bty = "o", bg = "white", box.col = "white",
         cex = 0.82, text.col = "#1F2937")
}

pdf(paste0(out_dir, "resolution_v17.pdf"), width = 7.2, height = 4.4)
draw_resolution_plot()
dev.off()

jpeg(paste0(out_dir, "resolution_v17.jpeg"), width = 2160, height = 1320, res = 300, quality = 100)
draw_resolution_plot()
dev.off()

if (interactive()) {
  dev.new(width = 7.2, height = 4.4, noRStudioGD = TRUE)
  draw_resolution_plot()
}
