import os
import pandas as pd
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from single_query_test import single_query


def main():
    # Configuration
    input_file = f"{os.path.dirname(os.path.abspath(__file__))}/test_cases.parquet"
    output_file = f"{os.path.dirname(os.path.abspath(__file__))}/test_results.parquet"
    url = os.environ.get("DJ_COPILOT_TEST_URL", "http://127.0.0.1:8080/process")
    max_workers = 10  # Number of concurrent threads, adjust based on server performance

    print(f"Reading data file: {input_file}")
    try:
        df = pd.read_parquet(input_file)
    except Exception as e:
        print(f"Failed to read parquet file: {e}")
        return

    print(f"Total {len(df)} queries to process")
    print(f"Columns: {df.columns.tolist()}")
    print(df.head())

    # Initialize result columns
    df["full_text"] = ""
    df["total_duration"] = None
    df["first_token_duration"] = None

    # Prepare task list
    tasks = []
    for idx, row in df.iterrows():
        if row.get("result", "") == "":
            # Keep track of the DataFrame index for each task
            tasks.append((idx, row["query"], url, None))

    # Parallel processing
    print(f"\nStarting parallel query processing, target server: {url}")
    print(f"Concurrent threads: {max_workers}")
    
    results_lock = Lock()
    completed_count = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_task = {
            executor.submit(single_query, query, url, session_id): (idx, query, url, session_id)
            for idx, query, url, session_id in tasks
        }
        
        # Use tqdm to show progress
        with tqdm(total=len(tasks), desc="Processing") as pbar:
            for future in as_completed(future_to_task):
                task_info = future_to_task[future]
                idx = task_info[0]
                try:
                    result_dict = future.result()
                    # Update DataFrame (use lock to ensure thread safety)
                    with results_lock:
                        df.at[idx, "full_text"] = result_dict.get("full_text", "")
                        df.at[idx, "total_duration"] = result_dict["total_duration"]
                        df.at[idx, "first_token_duration"] = result_dict["first_token_duration"]
                        completed_count += 1
                        if "status" in df.columns:
                            success_count = (df["status"] == "success").sum()
                        else:
                            success_count = completed_count
                        pbar.set_postfix({
                            "success": success_count,
                            "failed": completed_count - success_count
                        })
                except Exception as e:
                    print(f"\nException occurred while processing task: {e}")
                finally:
                    pbar.update(1)

    # Save results
    print(f"\nSaving results to: {output_file}")
    df.to_parquet(output_file, index=False)
    df.to_json(output_file.replace(".parquet", ".jsonl"), orient="records", lines=True, force_ascii=False)
    print(df.head())
    print("Save successful!")

    # Print statistics
    print("\n===== Processing Statistics =====")
    print(f"Total queries: {len(tasks)}")
    if (df["first_token_duration"].notna()).all() and (df["total_duration"].notna()).all():
        print(f"Average first token delay: {df['first_token_duration'].mean():.3f} seconds")
        print(f"Average total duration: {df['total_duration'].mean():.3f} seconds")
    else:
        print("Some queries failed to complete")


if __name__ == "__main__":
    main()

