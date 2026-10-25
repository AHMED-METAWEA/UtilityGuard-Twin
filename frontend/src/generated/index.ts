/**
 * Generated from contracts/v1/*.schema.json by json-schema-to-typescript.
 * DO NOT MODIFY: edits are lost. Run make gen-types.
 */

export type {
  CommonDefinitionsContractsV1,
  DetectorKey,
  EvidenceLabel,
  EvidenceLabelWithValue,
  Identifier,
  ModelVersion,
  MoneyConsistency,
  NullableUnit,
  Quality,
  Scalar,
  SchemaVersion,
  SensorKey,
  Sha256,
  StreamSource,
  TelemetryLabel,
  TemplateId,
  Unit,
  UtcTimestamp,
} from './common';

export type {
  Assumption,
  AssumptionSet,
} from './assumption-set';

export type {
  EvidenceRecord,
  Input,
} from './evidence-record';

export type {
  Incident,
} from './incident';

export type {
  BackgroundLeakageFault,
  BurstFault,
  CommsOutageFault,
  Fault,
  FireFlowFault,
  LeakGradualFault,
  LeakSuddenFault,
  PowerLossFault,
  PumpDegradationFault,
  PumpOutageFault,
  RunManifest,
  ScenarioConfiguration,
  SensorDriftFault,
  SensorDropoutFault,
  SensorNoiseGrowthFault,
  SensorOffsetFault,
  SensorStuckFault,
  ValveStateFault,
} from './run-manifest';

export type {
  BackgroundLeakageFault as ScenarioConfigBackgroundLeakageFault,
  BurstFault as ScenarioConfigBurstFault,
  CommsOutageFault as ScenarioConfigCommsOutageFault,
  Fault as ScenarioConfigFault,
  FireFlowFault as ScenarioConfigFireFlowFault,
  LeakGradualFault as ScenarioConfigLeakGradualFault,
  LeakSuddenFault as ScenarioConfigLeakSuddenFault,
  PowerLossFault as ScenarioConfigPowerLossFault,
  PumpDegradationFault as ScenarioConfigPumpDegradationFault,
  PumpOutageFault as ScenarioConfigPumpOutageFault,
  ScenarioConfiguration as ScenarioConfigScenarioConfiguration,
  SensorDriftFault as ScenarioConfigSensorDriftFault,
  SensorDropoutFault as ScenarioConfigSensorDropoutFault,
  SensorNoiseGrowthFault as ScenarioConfigSensorNoiseGrowthFault,
  SensorOffsetFault as ScenarioConfigSensorOffsetFault,
  SensorStuckFault as ScenarioConfigSensorStuckFault,
  ValveStateFault as ScenarioConfigValveStateFault,
} from './scenario-config';

export type {
  Quality as StreamEnvelopeQuality,
  StreamEnvelope,
  StreamReading,
  TickPayload,
} from './stream-envelope';

export type {
  Quality as TelemetryReadingQuality,
  TelemetryReading,
} from './telemetry-reading';
