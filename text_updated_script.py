import csv
import os
import re

def testRun(newLevels, newModel, newPromptAdaption, dataset_path):
    setParameters(newLevels, newModel, newPromptAdaption)
    
    saveName = f"result_L{newLevels}_M{newModel}_PA{newPromptAdaption}"

    # Initialize counters and evaluation arrays
    includedCount = 0
    notIncludedCount = 0
    unclearCount = 0
    resultRow = []
    
    eval = [[0, 0, 0, 0, 0] for _ in range(newLevels - 1)]  # [counts, correctlyIncluded, falselyIncluded, correctlyNotIncluded, falselyNotIncluded]
    
    for file_name in os.listdir(dataset_path):
        if file_name.endswith(".txt"):
            file_path = os.path.join(dataset_path, file_name)

            with open(file_path, "r", encoding="utf-8") as f:
                txt_data = f.read()

            # Extract fields based on text structure
            name = re.search(r"'Name': '(.+?)'", txt_data).group(1) if re.search(r"'Name': '(.+?)'", txt_data) else "N/A"
            pmid = re.search(r"'PMID': '(\d+)'", txt_data).group(1) if re.search(r"'PMID': '(\d+)'", txt_data) else "N/A"
            pmcid_match = re.search(r"'PMCID': '(\S+)'", txt_data)
            selection_criteria = re.search(r"'Selection_criteria': '(.+?)'", txt_data)
            clinical_questions = re.search(r"'Clinical_questions': '(.+?)'", txt_data).group(1) if re.search(r"'Clinical_questions': '(.+?)'", txt_data) else "N/A"
            excluded_studies_match = re.search(r"'Excluded_studies':\s*\[(.*?)\]", txt_data, re.DOTALL)
            included_studies_match = re.search(r"'Included_studies':\s*\[(.*?)\]", txt_data, re.DOTALL)
    
            # Extract numbers from Excluded Studies and Included Studies
            excluded_studies = re.findall(r"\d+", excluded_studies_match.group(1)) if excluded_studies_match else []
            included_studies = re.findall(r"\d+", included_studies_match.group(1)) if included_studies_match else []
    
            # Extracting Excluded Studies Characteristics
            excluded_characteristics_match = re.search(r"'Excluded_Studies_characteristics': \{(.*?)\}", txt_data, re.DOTALL)
            excluded_studies_characteristics = {}
            if excluded_characteristics_match:
                characteristics_data = excluded_characteristics_match.group(1)
                # Match each entry in the characteristics dictionary
                characteristics_entries = re.findall(r"'(\d+)': '(.+?)'", characteristics_data)
                for study_id, characteristic in characteristics_entries:
                    excluded_studies_characteristics[study_id] = characteristic
            
            title = name   
            abstract = (
                f"Clinical Questions: {clinical_questions}\n"
                f"Selection Criteria: {selection_criteria}\n"
                f"Included Studies: {', '.join(included_studies) if included_studies else 'None'}\n"
                f"Excluded Studies: {', '.join(excluded_studies) if excluded_studies else 'None'}\n"
                f"Excluded Studies Characteristics: {excluded_studies_characteristics if excluded_studies_characteristics else 'None'}"
            )
            included_label = "1"  

            # Prompt setup
            digitString = ", ".join(map(str, range(1, newLevels))) + f" or {newLevels}"
            instruction = f"On a scale from 1 (very low) to {newLevels} (very high), rate the relevance based on title, abstract, and criteria."
            prompt = f"{instruction} Title: {title}, Abstract: {abstract}, Relevant criteria: {relevantCriteria}"

            answer = getAnswer(prompt, newModel, instruction)
            answer = int(re.search(r'\d+', answer).group()) if re.search(r'\d+', answer) else -1

            # Count as unclear if answer is out of bounds
            if answer < 1 or answer > newLevels:
                unclearCount += 1
                continue

            # Store result
            singleResult = [file_name, title, abstract, included_label, answer, prompt]
            resultRow.append(singleResult)

            if included_label == "1":
                includedCount += 1
                for i in range(newLevels - 1):
                    if newLevels - i == answer:
                        eval[i][0] += 1  # Increase counter
                    if newLevels - i <= answer:
                        eval[i][1] += 1  # Correctly included
                    else:
                        eval[i][4] += 1  # Incorrectly not included
            else:
                notIncludedCount += 1
                for i in range(newLevels - 1):
                    if newLevels - i == answer:
                        eval[i][0] += 1  # Increase counter
                    if newLevels - i <= answer:
                        eval[i][2] += 1  # Falsely included
                    else:
                        eval[i][3] += 1  # Correctly not included

            # Intermediate save
            with open(f"{saveName}_single.csv", 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter=';', quotechar='"', quoting=csv.QUOTE_ALL)
                writer.writerow(singleResult)

    # Final output and evaluation metrics
    with open(f"{saveName}.csv", 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter=';', quotechar='"', quoting=csv.QUOTE_ALL)
        header = ["File Name", "Title", "Abstract", "Included-Label", "LLM Answer", "Prompt"]
        writer.writerow(header)
        writer.writerows(resultRow)

        # Metrics Calculation
        tp, sensitivity, precision, recall, f1, specificity = ([] for _ in range(6))
        for i in range(newLevels - 1):
            tp.append(eval[i][1] / eval[i][0] if eval[i][0] > 0 else -1)
            sensitivity.append(eval[i][1] / includedCount if includedCount > 0 else -1)
            precision.append(eval[i][1] / (eval[i][1] + eval[i][2]) if (eval[i][1] + eval[i][2]) > 0 else -1)
            recall.append(eval[i][1] / (eval[i][1] + eval[i][4]) if (eval[i][1] + eval[i][4]) > 0 else -1)
            f1.append(2 * ((precision[i] * recall[i]) / (precision[i] + recall[i])) if (precision[i] + recall[i]) > 0 else -1)
            specificity.append(eval[i][3] / notIncludedCount if notIncludedCount > 0 else -1)

            # Output metrics for each level in the file
            writer.writerow(["Metric", f"Level {newLevels - i}"])
            writer.writerow(["True Positive Rate", tp[i]])
            writer.writerow(["Sensitivity", sensitivity[i]])
            writer.writerow(["Specificity", specificity[i]])
            writer.writerow(["Precision", precision[i]])
            writer.writerow(["Recall", recall[i]])
            writer.writerow(["F1-Score", f1[i]])

    # Print summary information
    print(f"Included Publications: {includedCount}")
    print(f"Unclear Count: {unclearCount}")
