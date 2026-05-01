declare module "plotly.js-dist-min" {
  interface PlotlyStatic {
    react: (
      root: string | HTMLElement,
      data: object,
      layout?: object,
      config?: object,
    ) => Promise<void>;
    newPlot: (
      root: string | HTMLElement,
      data: object,
      layout?: object,
      config?: object,
    ) => Promise<void>;
  }
  const Plotly: PlotlyStatic;
  export default Plotly;
}
