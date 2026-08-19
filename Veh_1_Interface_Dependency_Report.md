# Veh_1 interface dependency analysis

- Model metadata: VCU_HIL_RCP/.em/Environments/env_1/env_1_Design/.ip/Models/Veh_1.json
- Model package: VCU_HIL_RCP/.em/Database/VCX/Base/Veh_1.vcx
- Input interfaces: 692; mapped to generated code: 690
- Output interfaces: 574; mapped to generated code: 574
- Generated-code assignment statements: 10449
- Output-to-input relation rows: 33; outputs without an external-input row: 554

## Files

- `Veh_1_Interface_Catalog.csv`: all mapped interfaces with direction, type, model path, group, notes, and injection hints.
- `Veh_1_Output_Input_Dependency.csv`: one static output-to-input dependency per row, with direct/indirect kind, evidence, and injection hints.
- `Veh_1_Input_Output_Impact.csv`: reverse index from each input to affected outputs, useful for choosing a fault-injection point.

## Scope and limitations

- Relations are obtained by statically tracing generated-code data flow backwards from `Veh_1_code_info_extio.xml` and `Veh_1.c`.
- `Direct input dependency` means the final output assignment reads the input directly; `Indirect input dependency` means intermediate variables are involved.
- Static paths do not mean the output changes in every operating condition: state machines, parameter overrides, saturation, guards, and cross-step state may suppress or delay changes.
- Use `Veh_1_Input_Output_Impact.csv` to choose a target input, then run single-variable step/out-of-range/freeze/dropout injection in HIL and monitor the output set in `Veh_1_Output_Input_Dependency.csv`.
