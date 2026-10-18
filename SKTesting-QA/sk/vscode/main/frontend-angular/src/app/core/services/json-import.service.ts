import { Injectable, inject } from '@angular/core';
import { RunConfigStore } from '../../state/run-config.store';
import { ModuleRegistryStore } from '../../state/module-registry.store';

export interface ImportPopulatedItem {
  path: string;
  value: string;
  controlId: string;
}

export interface ImportSkippedItem {
  path: string;
  reason: string;
}

export interface ImportResult {
  success: boolean;
  populated: ImportPopulatedItem[];
  skipped: ImportSkippedItem[];
  errors: string[];
  summary: string;
}

@Injectable({
  providedIn: 'root'
})
export class JsonImportService {
  private readonly configStore = inject(RunConfigStore);
  private readonly registryStore = inject(ModuleRegistryStore);

  importJson(jsonString: string): ImportResult {
    const result: ImportResult = {
      success: false,
      populated: [],
      skipped: [],
      errors: [],
      summary: ''
    };

    let raw: Record<string, any>;
    try {
      raw = JSON.parse(jsonString);
    } catch (e: any) {
      result.errors.push('JSON parse error: ' + (e?.message || 'Invalid JSON syntax.'));
      return result;
    }

    if (typeof raw !== 'object' || raw === null || Array.isArray(raw)) {
      result.errors.push('Top-level JSON value must be an object.');
      return result;
    }

    // Version check
    const version = String(raw['config_version'] || '');
    if (version && version !== '1.0') {
      result.errors.push(`Unsupported config_version '${version}'. Expected '1.0'.`);
      return result;
    }

    // 1. Environment & Project
    if (raw['project'] && typeof raw['project'] === 'object') {
      if (raw['project']['environment']) {
        const env = String(raw['project']['environment']).toUpperCase();
        if (['PRODUCTION', 'STAGING', 'QA', 'DEV'].includes(env)) {
          this.configStore.environments.set(env);
          result.populated.push({ path: 'project.environment', value: env, controlId: 'environments' });
        } else {
          result.skipped.push({ path: 'project.environment', reason: `Unknown environment '${env}'` });
        }
      }
    }

    // 2. Execution Settings
    if (raw['execution'] && typeof raw['execution'] === 'object') {
      const ex = raw['execution'];
      if (ex['browser']) {
        const b = String(ex['browser']).toLowerCase();
        this.configStore.browsername.set(b);
        result.populated.push({ path: 'execution.browser', value: b, controlId: 'browsername' });
      }
      if (ex['branch']) {
        this.configStore.branch.set(String(ex['branch']));
        result.populated.push({ path: 'execution.branch', value: String(ex['branch']), controlId: 'branch' });
      }
      if (ex['company_name']) {
        this.configStore.companyName.set(String(ex['company_name']));
        result.populated.push({ path: 'execution.company_name', value: String(ex['company_name']), controlId: 'company_name' });
      }
      if (ex['timeout'] !== undefined) {
        this.configStore.defaultTimeout.set(Number(ex['timeout']));
        result.populated.push({ path: 'execution.timeout', value: String(ex['timeout']), controlId: 'DEFAULT_TIMEOUT' });
      }
      if (ex['short_timeout'] !== undefined) {
        this.configStore.shortTimeout.set(Number(ex['short_timeout']));
        result.populated.push({ path: 'execution.short_timeout', value: String(ex['short_timeout']), controlId: 'SHORT_TIMEOUT' });
      }
      if (ex['wait_after_action'] !== undefined) {
        this.configStore.waitAfterAction.set(Number(ex['wait_after_action']));
        result.populated.push({ path: 'execution.wait_after_action', value: String(ex['wait_after_action']), controlId: 'WAIT_AFTER_ACTION' });
      }
    }

    // 3. Test Data / Credentials
    if (raw['test_data'] && typeof raw['test_data'] === 'object') {
      const td = raw['test_data'];
      if (td['email']) {
        this.configStore.email.set(String(td['email']));
        result.populated.push({ path: 'test_data.email', value: String(td['email']), controlId: 'email' });
      }
      if (td['password']) {
        this.configStore.password.set(String(td['password']));
        result.populated.push({ path: 'test_data.password', value: '••••••••', controlId: 'password' });
      }
      if (td['use_custom_login'] !== undefined) {
        const val = Boolean(td['use_custom_login']);
        this.configStore.useCustomLogin.set(val);
        result.populated.push({ path: 'test_data.use_custom_login', value: String(val), controlId: 'use_custom_login' });
      }
      if (td['qs_audit_name']) {
        this.configStore.qsAuditName.set(String(td['qs_audit_name']));
        result.populated.push({ path: 'test_data.qs_audit_name', value: String(td['qs_audit_name']), controlId: 'qs-audit-name' });
      }
      if (td['qs_a1']) {
        this.configStore.qsA1.set(String(td['qs_a1']));
        result.populated.push({ path: 'test_data.qs_a1', value: String(td['qs_a1']), controlId: 'qs-a1' });
      }
      if (td['qs_a2']) {
        this.configStore.qsA2.set(String(td['qs_a2']));
        result.populated.push({ path: 'test_data.qs_a2', value: String(td['qs_a2']), controlId: 'qs-a2' });
      }
    }

    // 4. Module Toggles
    if (raw['modules'] && typeof raw['modules'] === 'object') {
      const mods = raw['modules'];
      const allModules = this.registryStore.modules();
      for (const [key, val] of Object.entries(mods)) {
        const isEnabled = Boolean(val);
        const match = allModules.find(m => m.name === key || m.flag === key || m.display.toLowerCase() === key.toLowerCase());
        if (match) {
          this.registryStore.setModuleEnabled(match.idx, isEnabled);
          result.populated.push({ path: `modules.${key}`, value: String(isEnabled), controlId: match.cb });
        } else {
          result.skipped.push({ path: `modules.${key}`, reason: 'No matching module registered in runner' });
        }
      }
    }

    result.success = result.errors.length === 0;
    result.summary = result.success
      ? `Successfully imported ${result.populated.length} configuration values.`
      : `Import completed with ${result.errors.length} error(s).`;

    return result;
  }
}
