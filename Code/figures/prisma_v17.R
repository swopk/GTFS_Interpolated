# Figure 1: feed selection flow, with counts read from the data files.
graphics.off()

d <- read.csv("../../data_files/feed_data_v2.csv")
f <- read.csv("../../feed_failures.csv")
m <- read.csv("../../feed_metadata.csv", colClasses = "character")
out_dir <- ""

fmt <- function(x) format(x, big.mark = ",")
n_catalogue <- 4431
n_retained <- nrow(m)
n_test <- n_catalogue - n_retained
n_failed <- sum(m$download_status == "failed")
n_downloaded <- n_retained - n_failed
n_byte <- sum(m$duplicate_of != "")
n_unique <- nrow(d) + nrow(f)
n_network <- n_downloaded - n_byte - n_unique

reasons <- table(f$fail_reason)
n_ins <- sum(reasons[names(reasons) == "insufficient fixed-route bus service"])
n_date <- sum(reasons[names(reasons) == "no usable service date"])
n_tab <- sum(reasons[names(reasons) == "missing required table"])
n_err <- nrow(f) - n_ins - n_date - n_tab

main_boxes <- list(
  c("Feeds listed in the Mobility Database catalog", fmt(n_catalogue)),
  c("Feeds retained after removing test entries", fmt(n_retained)),
  c("Feeds downloaded", fmt(n_downloaded)),
  c("Unique feeds after deduplication", fmt(n_unique)),
  c("Feeds analyzed (usable fixed-route bus schedule)", fmt(nrow(d)))
)

side_boxes <- list(
  c("Development or test entries", fmt(n_test), ""),
  c("Download failed", fmt(n_failed), ""),
  c("Duplicates", fmt(n_byte + n_network),
    paste0(fmt(n_byte), " byte-identical; ", fmt(n_network), " same network")),
  c("No usable bus schedule", fmt(nrow(f)),
    paste0(fmt(n_ins), " low fixed-route bus service; ", n_date,
           " no service date;\n", n_tab, " missing table; ", n_err, " unreadable"))
)

ink <- "#1F2937"
line_col <- "#9CA3AF"
accent <- "#3B629B"

draw_prisma <- function() {
  par(mar = c(0, 0, 0, 0), family = "sans")
  plot.new()
  plot.window(xlim = c(0, 100), ylim = c(2, 98), yaxs = "i")

  ys <- c(90, 70, 50, 30, 10)
  bx <- c(2, 50)
  h <- 6.5

  for (i in seq_along(ys)) {
    last <- i == length(ys)
    rect(bx[1], ys[i] - h, bx[2], ys[i] + h,
         col = if (last) "#EAF0F7" else "white",
         border = if (last) accent else ink, lwd = if (last) 1.4 else 0.8)
    text(mean(bx), ys[i] + 2.2, main_boxes[[i]][1], cex = 0.80, col = ink)
    text(mean(bx), ys[i] - 2.6, paste("n =", main_boxes[[i]][2]), cex = 0.92,
         font = 2, col = if (last) accent else ink)
    if (i < length(ys)) {
      arrows(mean(bx), ys[i] - h, mean(bx), ys[i + 1] + h, length = 0.08,
             lwd = 0.9, col = ink)
    }
  }

  sx <- c(57, 99)
  for (i in seq_along(side_boxes)) {
    y <- (ys[i] + ys[i + 1]) / 2
    sh <- if (side_boxes[[i]][3] == "") 3.6 else 5.6
    rect(sx[1], y - sh, sx[2], y + sh, col = "white", border = line_col, lwd = 0.8)
    arrows(mean(bx), y, sx[1], y, length = 0.06, col = line_col, lwd = 0.9)
    if (side_boxes[[i]][3] == "") {
      text(mean(sx), y, paste0(side_boxes[[i]][1], " (n = ", side_boxes[[i]][2], ")"),
           cex = 0.78, col = ink)
    } else {
      text(mean(sx), y + 2.6, paste0(side_boxes[[i]][1], " (n = ", side_boxes[[i]][2], ")"),
           cex = 0.78, col = ink)
      text(mean(sx), y - 1.9, side_boxes[[i]][3], cex = 0.66, col = "#4B5563")
    }
  }
}

pdf(paste0(out_dir, "prisma_v17.pdf"), width = 8.0, height = 5.3)
draw_prisma()
dev.off()

jpeg(paste0(out_dir, "prisma_v17.jpeg"), width = 2400, height = 1590, res = 300, quality = 100)
draw_prisma()
dev.off()

if (interactive()) {
  dev.new(width = 8.0, height = 5.3, noRStudioGD = TRUE)
  draw_prisma()
}
