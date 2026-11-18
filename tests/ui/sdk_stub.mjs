// Stand-in for the host-provided "@kirocrew/app-sdk" (resolved by the Gateway's import map at runtime).
import { useEffect } from "react";
export const useAppApi = () => globalThis.__api;
export const useAppEvents = () => {};
export const useAppInfo = () => ({ version: "test" });
export const useNotify = () => () => {};
export const useEffectNoop = useEffect;
