import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const config: NextConfig = {
  turbopack: {},
  transpilePackages: ["radix-ui"],
};

export default withNextIntl(config);
