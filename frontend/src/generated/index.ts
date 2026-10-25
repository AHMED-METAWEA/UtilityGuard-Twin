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
  ScenarioConfiguration,
  SensorDriftFault,
  SensorDropoutFault,
  SensorNoiseGrowthFault,
  SensorOffsetFault,
  SensorStuckFault,
  ValveStateFault,
} from './scenario-config';

export type {
  RunManifest,
} from './run-manifest';

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
