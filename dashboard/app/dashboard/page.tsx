// The dashboard now lives at /dashboard; the public landing owns "/".
// The shell itself stays in app/DashboardHome.tsx so its relative imports
// (./hooks, ./components, ./lib) keep resolving unchanged.
export { default } from "../DashboardHome";
