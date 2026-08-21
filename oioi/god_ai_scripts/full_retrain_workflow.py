"""
full_retrain_workflow.py - Complete automated retraining pipeline
(Fixed: Adds dataset summary generation step)
"""

import subprocess
import shutil
from pathlib import Path
import time
import json
import sys

# Paths
ORIGINAL_DATASET = Path("final_dataset")
BACKUP_DATASET = Path("final_dataset_backup")
CLEANED_DATASET = Path("cleaned_dataset")
MODELS_BACKUP = Path("models_backup")

class RetrainingWorkflow:
    def __init__(self):
        self.start_time = time.time()
        self.steps_completed = []
        
    def log_step(self, step_name, status="[OK]"):
        """Log completed step"""
        elapsed = time.time() - self.start_time
        self.steps_completed.append({
            'step': step_name,
            'status': status,
            'time': elapsed
        })
        print(f"\n{status} {step_name} (elapsed: {elapsed:.1f}s)")
    
    def run_command(self, cmd, description):
        """Run a shell command and stream output in real-time"""
        print(f"\n[>] {description}...")
        
        # Use sys.executable to ensure we use the same python interpreter
        if cmd.startswith("python "):
            cmd = f"{sys.executable} {cmd[7:]}"
            
        try:
            # REMOVED: capture_output=True
            # ADDED: check=True (to catch errors), stdout/stderr default to None (inherit from parent)
            subprocess.run(
                cmd,
                shell=True,
                check=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            return True
            
        except subprocess.CalledProcessError as e:
            # Note: e.stderr won't be available here because we didn't capture it.
            # It was already printed to the screen when the error happened.
            print(f"Error executing command: {cmd}")
            return False
    
    def backup_current_state(self):
        """Step 1: Backup current dataset and models"""
        print("\n" + "="*70)
        print("STEP 1: Backing up current state")
        print("="*70)
        
        # Backup dataset
        if ORIGINAL_DATASET.exists() and not BACKUP_DATASET.exists():
            print(f"Backing up {ORIGINAL_DATASET} -> {BACKUP_DATASET}")
            shutil.copytree(ORIGINAL_DATASET, BACKUP_DATASET)
        elif BACKUP_DATASET.exists():
            print(f"Backup already exists at {BACKUP_DATASET}, skipping copy.")
        
        # Backup models
        if not MODELS_BACKUP.exists():
            MODELS_BACKUP.mkdir()
        
        model_files = [
            "best_toxic_detector.pth",
            "best_toxic_detector.onnx"
        ]
        
        for model_file in model_files:
            if Path(model_file).exists():
                shutil.copy2(
                    model_file, 
                    MODELS_BACKUP / f"{Path(model_file).stem}_backup{Path(model_file).suffix}"
                )
        
        self.log_step("Backup completed")
    
    def clean_dataset(self):
        """Step 2: Run auto-cleaning"""
        print("\n" + "="*70)
        print("STEP 2: Auto-cleaning dataset")
        print("="*70)
        
        if self.run_command(
            "python auto_dataset_cleaner.py",
            "Running dataset cleaner"
        ):
            self.log_step("Dataset cleaned")
            return True
        else:
            print("Cleaning failed!")
            return False
    
    def swap_datasets(self):
        """Step 3: Swap cleaned dataset with original"""
        print("\n" + "="*70)
        print("STEP 3: Swapping datasets")
        print("="*70)
        
        if not CLEANED_DATASET.exists():
            print("Cleaned dataset not found!")
            return False
        
        # Remove old final_dataset
        if ORIGINAL_DATASET.exists():
            shutil.rmtree(ORIGINAL_DATASET)
        
        # Rename cleaned -> final
        shutil.move(str(CLEANED_DATASET), str(ORIGINAL_DATASET))
        
        print(f" {CLEANED_DATASET} -> {ORIGINAL_DATASET}")
        self.log_step("Datasets swapped")
        return True

    def generate_summary(self):
        """Step 3.5: Generate dataset summary (CRITICAL FIX)"""
        print("\n" + "="*70)
        print("STEP 3.5: Generating dataset summary")
        print("="*70)
        
        if self.run_command(
            "python dataset_summary_script.py",
            "Calculating class weights"
        ):
            self.log_step("Summary generated")
            return True
        else:
            print("Summary generation failed!")
            return False
    
    def retrain_model(self):
        """Step 4: Retrain model with cleaned data"""
        print("\n" + "="*70)
        print("STEP 4: Retraining model (this will take 10-30 minutes)")
        print("="*70)
        
        if self.run_command(
            "python train_toxic_detector.py",
            "Training new model"
        ):
            self.log_step("Model retrained")
            return True
        else:
            print("Training failed!")
            return False
    
    def convert_to_onnx(self):
        """Step 5: Convert to ONNX"""
        print("\n" + "="*70)
        print("STEP 5: Converting to ONNX")
        print("="*70)
        
        if self.run_command(
            "python convert_to_onnx_and_tflite.py",
            "Converting model"
        ):
            self.log_step("Converted to ONNX")
            return True
        else:
            print("Conversion failed!")
            return False
    
    def validate_improvements(self):
        """Step 6: Test new model vs old model"""
        print("\n" + "="*70)
        print("STEP 6: Validating improvements")
        print("="*70)
        
        # Test with new model
        print("\nTesting NEW model:")
        self.run_command(
            "python inference.py",
            "Running inference"
        )
        
        self.log_step("Validation complete")
    
    def generate_summary_report(self):
        """Step 7: Generate final summary"""
        print("\n" + "="*70)
        print("RETRAINING WORKFLOW COMPLETE!")
        print("="*70)
        
        total_time = time.time() - self.start_time
        
        print(f"\nTotal time: {total_time/60:.1f} minutes")
        print("\nSteps completed:")
        for step in self.steps_completed:
            print(f"  {step['status']} {step['step']}")
        
        print("\nFiles:")
        print(f"  * Backup dataset:     {BACKUP_DATASET}")
        print(f"  * Backup models:      {MODELS_BACKUP}")
        print(f"  * New model (PyTorch): best_toxic_detector.pth")
        print(f"  * New model (ONNX):    best_toxic_detector.onnx")
        print(f"  * Cleaning report:    cleaning_report/cleaning_report.html")
    
    def run(self):
        """Execute full workflow"""
        try:
            
            
            # --- FIXED STEP ---
            if not self.generate_summary():
                return
            # ------------------
            
            if not self.retrain_model():
                return
            
            if not self.convert_to_onnx():
                return
            
            self.validate_improvements()
            self.generate_summary_report()
            
        except KeyboardInterrupt:
            print("\n\nWorkflow interrupted by user!")
        except Exception as e:
            print(f"\n\nUnexpected error: {e}")


def main():
    print("""
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║     AUTOMATED RETRAINING WORKFLOW (FIXED)                         ║
║     Fix False Positives & Retrain Model                           ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
""")
    
    response = input("\nProceed? (yes/no): ").strip().lower()
    
    if response in ['yes', 'y']:
        workflow = RetrainingWorkflow()
        workflow.run()
    else:
        print("Cancelled.")


if __name__ == "__main__":
    main()