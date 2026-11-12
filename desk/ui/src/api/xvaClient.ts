// Cliente HTTP del corte 9 (XVA y crédito sintético). Usa la misma capa `request` que `client.ts`.
import { apiRequest } from './client';
import type {
  CreditCurveBody,
  CreditCurvesResponse,
  CreditCurve,
  XvaIncrementalBody,
  XvaIncrementalResponse,
  XvaParamsBody,
  XvaParamsResponse,
  XvaResponse,
} from './xvaTypes';

export function getXva(snapshot: string): Promise<XvaResponse> {
  return apiRequest('GET', `/xva?snapshot=${encodeURIComponent(snapshot)}`);
}

export function getXvaParams(): Promise<XvaParamsResponse> {
  return apiRequest('GET', '/xva/params');
}

export function putXvaParams(body: XvaParamsBody): Promise<XvaParamsResponse> {
  return apiRequest('PUT', '/xva/params', body);
}

export function xvaIncremental(body: XvaIncrementalBody): Promise<XvaIncrementalResponse> {
  return apiRequest('POST', '/xva/incremental', body);
}

export function getCreditCurves(snapshot: string): Promise<CreditCurvesResponse> {
  return apiRequest('GET', `/credit/curves?snapshot=${encodeURIComponent(snapshot)}`);
}

export function putCreditCurve(entity: string, body: CreditCurveBody): Promise<CreditCurve> {
  return apiRequest('PUT', `/credit/curves/${encodeURIComponent(entity)}`, body);
}
