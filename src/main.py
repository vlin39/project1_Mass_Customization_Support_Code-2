import json
from pathlib import Path
from argparse import ArgumentParser

from dimacs_parser import DimacsParser
from model_timer import Timer
from solver import solve_sat


def _format_solution(num_vars: int, assignment) -> str:
    parts = []
    for v in range(1, num_vars + 1):
        av = assignment[v]
        val = (av == 1)  # unassigned defaults to false
        parts.append(f"{v} {'true' if val else 'false'}")
    return " ".join(parts)


def main(args):
    input_file = args.input_file
    filename = Path(input_file).name

    timer = Timer()
    timer.start()

    instance = DimacsParser.parse_cnf_file(input_file)
    sat, assignment = solve_sat(
        num_vars=instance.numVars,
        clauses_as_sets=instance.clauses,
        active_vars=instance.vars,  
    )

    timer.stop()
    time_str = f"{timer.getTime():.2f}" 
    inst_json = json.dumps(filename)

    if sat:
        sol = _format_solution(instance.numVars, assignment)
        sol_json = json.dumps(sol)
        print(f'{{"Instance": {inst_json}, "Time": {time_str}, "Result": "SAT", "Solution": {sol_json}}}')
    else:
        print(f'{{"Instance": {inst_json}, "Time": {time_str}, "Result": "UNSAT"}}')


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("input_file", type=str)
    args = parser.parse_args()
    main(args)
