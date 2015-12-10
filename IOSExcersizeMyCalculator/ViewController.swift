//
//  ViewController.swift
//  retro-calculator
//
//  Created by Mark Price on 8/1/15.
//  Copyright © 2015 devslopes. All rights reserved.
//

import UIKit
import AVFoundation

class ViewController: UIViewController {
    
    enum Operation: String {
        case Divide = "/"
        case Multiply = "*"
        case Subtract = "-"
        case Add = "+"
        case Clear = "c"
        case Minus = "m"
        case Percent = "p"
        case Empty = "Empty"
    }
    
    
    @IBOutlet weak var outputLbl: UILabel!
    
    
    var runningNumber = ""
    var leftValStr = ""
    var rightValStr = ""
    var currentOperation: Operation = Operation.Empty
    var result = ""
    
    override func viewDidLoad() {
        super.viewDidLoad()
        
        
        
    }
    
    func resetEnvironment ()
    {
        runningNumber = ""
        leftValStr = ""
        rightValStr = ""
        currentOperation = Operation.Empty
        result = ""
    }
    
    @IBAction func numberPressed(btn: UIButton!) {
        
        runningNumber += "\(btn.tag)"
        outputLbl.text = runningNumber
        
        print ("num pressed =\(runningNumber) rvalStr=\(rightValStr) lvalStr=\(leftValStr) op=\(currentOperation) label==\(outputLbl.text)")
        
    }
    
    @IBAction func onClearPressed(sender: AnyObject) {
        processUnaryOperation(Operation.Clear)
    }
    
    @IBAction func onMinusPressed(sender: AnyObject) {
        processUnaryOperation(Operation.Minus)
    }
    @IBAction func onPercentPressed(sender: AnyObject) {
        processUnaryOperation(Operation.Percent)
    }
    
    
    @IBAction func onDividePressed(sender: AnyObject) {
        processOperation(Operation.Divide)
    }
    
    @IBAction func onMultiplyPressed(sender: AnyObject) {
        processOperation(Operation.Multiply)
    }
    
    @IBAction func onSubtractPressed(sender: AnyObject) {
        processOperation(Operation.Subtract)
    }
    
    @IBAction func onAddPressed(sender: AnyObject) {
        processOperation(Operation.Add)
    }
    
    @IBAction func onEqualPressed(sender: AnyObject) {
        processOperation(currentOperation)
    }
    
    func processUnaryOperation(op: Operation) {
        
        
        if op != Operation.Empty {
            //Run some math
            
            if leftValStr != "" {
                
                print ("Unityt operation called \(currentOperation) left=\(leftValStr)")
                if op == Operation.Clear {
                    result = "\(Double(leftValStr)! - Double(leftValStr)!)"
                }else if op == Operation.Minus {
                    result = "\(0 - Double(leftValStr)! )"
                }else if op == Operation.Percent {
                    result = "\(Double(leftValStr)! / 100.0)"
                }
                
                runningNumber = ""
                rightValStr = ""
                
                currentOperation = Operation.Empty
                if (op == Operation.Clear){
                    currentOperation = Operation.Clear
                }
                
                leftValStr = result
                outputLbl.text = result
                
            }
            
            print ("Calculating res=\(result)")
            currentOperation = op
        } else {
            //This is the first time an operator has been pressed
            leftValStr = runningNumber
            runningNumber = ""
            currentOperation = op
        }
    }
    
    func processOperation(op: Operation) {
        
        print ("Process:rnum=\(runningNumber) rvalStr=\(rightValStr) lvalStr=\(leftValStr) op=\(currentOperation)")
        if currentOperation != Operation.Empty && currentOperation != Operation.Clear {
            //Run some math
            
            //A user selected an operator, but then selected another operator without
            //first entering a number
            if runningNumber != "" {
                rightValStr = runningNumber
                runningNumber = ""
                
                
                if currentOperation == Operation.Multiply {
                    result = "\(Double(leftValStr)! * Double(rightValStr)!)"
                } else if currentOperation == Operation.Divide {
                    result = "\(Double(leftValStr)! / Double(rightValStr)!)"
                } else if currentOperation == Operation.Subtract {
                    result = "\(Double(leftValStr)! - Double(rightValStr)!)"
                } else if currentOperation == Operation.Add {
                    result = "\(Double(leftValStr)! + Double(rightValStr)!)"
                }
                
                leftValStr = result
                outputLbl.text = result
                print ("Calculating res=\(result)")
            }
            
            
            currentOperation = op
            
        } else {
            //This is the first time an operator has been pressed
            leftValStr = runningNumber
            runningNumber = ""
            currentOperation = op
        }
    }
    
    
}



