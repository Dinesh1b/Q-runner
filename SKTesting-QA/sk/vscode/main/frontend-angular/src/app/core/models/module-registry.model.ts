/**
 * module-registry.model.ts
 * Type definitions matching modules.json exactly.
 */

export type SessionType = 'auditor1' | 'auditor2';

export interface ModuleDef {
  idx: number;
  flag: string;
  name: string;
  display: string;
  icon: string;
  group: number;
  session: SessionType;
  workflow: string;
  cb: string;
  tgl: string;
  alt_flag?: string;
  enabled?: boolean;
}

export interface GroupDef {
  idx: number;
  name: string;
  range: [number, number];
  enabled?: boolean;
}

export interface ModulesApiResponse {
  groups: GroupDef[];
  modules: ModuleDef[];
}
