# Data-Juicer Q&A Copilot Tests

### Usage

#### 1. Start Serving

See [../README.md](../README.md) for instructions on starting the server. 

#### 2. (Optional) Setting `DJ_COPILOT_TEST_URL`

```bash
export DJ_COPILOT_TEST_URL="your.url.here/process"
```

For example,

```bash
export DJ_COPILOT_TEST_URL="http://127.0.0.1:8080/process"
```

You can skip this step if the serving URL is `http://127.0.0.1:8080/process`

#### 3.1 Single Query Test for Fast Evaluation

```bash
python single_query_test.py --query <your query here>
```

For example,

```bash
python single_query_test.py --query "Introduce alphanumeric_filter"
```

You will see a formatted summary

```plain text
===== Query =====
<query>

===== Full Text =====
<response>

===== Query Stats =====
First Token Duration: <first token time> s
Total Time: <total time> s
```

#### 3.2 Parallel Evaluation for multiple test cases

Test cases are 

```bash
python run_tests.py
```

Query cases are saved in `test_cases.parquet`. You can customize new test cases by modifying it.

```plain text
Columns: ['query', 'type', 'lang']
                                       query          type lang
0              Introduce alphanumeric_filter   operator_qa   en
1                     介绍alphanumeric_filter   operator_qa   zh
2                        Introduce DJ-Agents  submodule_qa   en
3                               介绍DJ-Agents  submodule_qa   zh
4  Tell me about the base class of operators    concept_qa   en
...
```

The results will be saved in `test_results.parquet`, with new columns `total_duration`, `first_toen_duration`, `full_text`.