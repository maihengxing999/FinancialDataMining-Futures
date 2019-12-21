rm(list=ls())
library(readxl)
CU9999 <- read_excel("C:/Users/steve/Desktop/test.xlsx",
                     col_types = c("numeric"))
lnp <- as.ts(log(CU9999['ÊÕÅÌ']))

slope <- c()
R_Square <- c()
t_value <- c()
for (t in 1:1000){
  # print(t)
  rt <- diff(lnp, lag=t)*100
  n <- length(rt)
  rt.his <- rt[-(n-t+1):-n]
  rt.fut <- rt[-1:-t]
  model <- lm(rt.fut~rt.his)
  # print(model$coefficients['rt.his'])
  slope <- append(slope, model$coefficients['rt.his'])
  # print('t-value')
  tv <- summary(model)$coefficients[2,3]
  # print(tv)
  t_value <- append(t_value, t)
  # print('R square')
  R2 <- summary(model)$r.squared
  # print(R2)
  # print('-----------')
  R_Square <- append(R_Square, R2)
  # if (t==1) print(summary(model))
}
par(mfrow=c(1,3))
plot(slope)
plot(R_Square)
plot(t_value)