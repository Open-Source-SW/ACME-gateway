;;
;;	toggleLightswitch.as
;;
;;	Implementation of a toggle lightswitch for the Lightbulb Demo
;;
;;	(c) 2023 by Andreas Kraft
;;	License: BSD 3-Clause License. See the LICENSE file for further details.
;;
;;	This script is execued by pressing the toggle button in the TUI.
;;

@category Lightbulb Demo
@name Toggle Lightswitch
@tuiTool
@description ## Lightbulb Demo - Toggle Switch\n\nThis page is used to toggle the status of the *Lightswitch* from **on** to **off** and vice versa. This will also create a *Notification* that is send to the subscribed *Lightbulb*.\nPress the **Toggle Lightswitch** button to toggle the *Lightswitch* status.\nSwitch to the *Lightbulb* tool to see the effect.\n\n
@tuiExecuteButton Toggle Lightswitch
@tuiAutoRun


;; Include some helper functions
(include-script "functions")


(setq on "
     ┌───────────────┐
     │       [green1]■[/green1]       │
     │     ┌───┐     │
     │     │   │     │
     │     │   │     │
     │  ┌──┴───┴──┐  │
     │  │   ON    │  │
     │  └─────────┘  │
     │               │
     │               │
     │               │
     │       [green1]■[/green1]       │
     └───────────────┘
")
(setq off "
     ┌───────────────┐
     │       [red]▢[/red]       │
     │               │
     │               │
     │               │
     │  ┌─────────┐  │
     │  │   OFF   │  │
     │  └──┬───┬──┘  │
     │     │   │     │
     │     │   │     │
     │     └───┘     │
     │       [red]▢[/red]       │
     └───────────────┘
")

;; Define the lightswitch status retrieval function.
;; This function tries to retrieve the current status from the storage first. If it is not available, it retrieves the latest
;; ContentInstance from the CSE. The fallback is always "off".
;; We could retrieve the current status from the CSE directly, but this would require a GET request to the CSE for every
;; status change. To emulate a real device, we use the storage here.
(defun get-lightswitch-status ()
  ((if (has-storage "lightswitchDemo" "status")
     (get-storage "lightswitchDemo" "status")
     ((setq response (retrieve-resource "CDemoLightswitch" "${(get-config \"cse.resourceName\")}/CDemoLightswitch/switchContainer/la"))
      (if (== (get-response-status response) 2000)
        ((setq cin (get-response-resource response))
         (if (has-json-attribute cin "m2m:cin/con")
           (get-json-attribute cin "m2m:cin/con")))
        ("off"))) )))	;;Fallback is always off for all errors


(defun print-lightswitch (st)
  ((clear-console)
   ;; Print the lightswitch status as ASCII art. Transform the value of "st" to a symbol,
   ;; ie. the value "on" or "off", evaluate it as a symbol (ie as a variable) and print its value.
   (print (eval (to-symbol st)))))


;; Define the lightswitch status setting function.
;; This function sets the lightswitch status in the storage and creates a new ContentInstance in the CSE.
(defun set-lightswitch-status (st)
  ((print-lightswitch st)
   (create-resource "CDemoLightswitch" "${(get-config \"cse.resourceName\")}/CDemoLightswitch/switchContainer" 
      { "m2m:cin": {
          "con" : "${(st)}"
      }})
   (put-storage "lightswitchDemo" "status" st)))


;; Check if this script is executed by the autorun mechanism. If so, just set the lightswitch status and quit.
(if (is-defined 'tui.autorun)
  (if (== tui.autorun true)
    ((print-lightswitch (get-lightswitch-status))
     (quit))))


;; Toggle the lightswitch status
(case (get-lightswitch-status)
  ("on"   (set-lightswitch-status "off"))
  ("off"  (set-lightswitch-status "on")))
