import onnx
import numpy as np
from onnx import helper, numpy_helper

# Load the model
model = onnx.load("toxic_detector.onnx")

# Find the problematic Conv node
problem_node = None
for node in model.graph.node:
    if node.name == "node_Conv_681" or "Conv_681" in node.name:
        problem_node = node
        print(f"Found problematic node: {node.name}")
        print(f"Op type: {node.op_type}")
        print(f"Inputs: {node.input}")
        print(f"Outputs: {node.output}")
        break

if problem_node:
    # Check the weight tensor
    weight_name = problem_node.input[1] if len(problem_node.input) > 1 else None
    
    if weight_name:
        print(f"\nLooking for weight tensor: {weight_name}")
        
        # Search in initializers
        for init in model.graph.initializer:
            if init.name == weight_name:
                weight_array = numpy_helper.to_array(init)
                print(f"Weight shape: {weight_array.shape}")
                print(f"Weight dtype: {weight_array.dtype}")
                print(f"Expected shape for Conv: (out_channels, in_channels, kH, kW)")
                
                # Check if shape is unusual
                if len(weight_array.shape) != 4:
                    print(f"ERROR: Weight has {len(weight_array.shape)} dimensions, expected 4!")
                    print("This is the source of the problem.")
                    
                    # Attempt to reshape if possible
                    if len(weight_array.shape) == 2:
                        print("\nAttempting to fix by reshaping 2D to 4D...")
                        # Common fix: reshape (out, in) to (out, in, 1, 1)
                        new_shape = (weight_array.shape[0], weight_array.shape[1], 1, 1)
                        weight_array_fixed = weight_array.reshape(new_shape)
                        
                        # Update the initializer
                        new_init = numpy_helper.from_array(weight_array_fixed, init.name)
                        model.graph.initializer.remove(init)
                        model.graph.initializer.append(new_init)
                        
                        print(f"Reshaped to: {new_shape}")
                        
                        # Save the fixed model
                        onnx.save(model, "toxic_detector_fixed.onnx")
                        print("\nFixed model saved as: toxic_detector_fixed.onnx")
                    else:
                        print(f"Cannot auto-fix: unexpected shape {weight_array.shape}")
                else:
                    print(f"Weight shape looks correct: {weight_array.shape}")
                    print("The issue might be with the weight layout or the model export.")
                
                break
else:
    print("Could not find the problematic node. Listing all Conv nodes:")
    conv_count = 0
    for node in model.graph.node:
        if node.op_type == "Conv":
            conv_count += 1
            if conv_count >= 680:  # Around the problematic node
                print(f"  {node.name}: inputs={node.input}")
    
print("\n" + "="*60)
print("RECOMMENDATION:")
print("="*60)
print("If the weight shape is unusual, you need to re-export the model.")
print("Check your PyTorch export code and ensure all weights are properly formatted.")
